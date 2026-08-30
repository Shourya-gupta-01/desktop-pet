import os
import sys
import yaml
import inspect
import logging
import importlib.util
import time
from typing import Dict, List, Set, Optional, Tuple, Any

from core.base_plugin import BasePlugin, PluginManifest, PluginContext, IncomingEvent


class PluginLoader:
    """
    Discovers, validates, instantiates, and routes events to Desktop Pet plugins.
    Ensures safe error isolation so individual plugin failures never crash the core.
    """

    def __init__(self, plugins_dir: str, context: PluginContext):
        self.plugins_dir = os.path.abspath(plugins_dir)
        self.context = context
        self.logger = logging.getLogger("PluginLoader")
        
        # Loaded plugin instances: { plugin_name: instance }
        self.plugins: Dict[str, BasePlugin] = {}
        
        # Event routing table: { subscription_pattern: [plugin_instances] }
        self.subscriptions: Dict[str, List[BasePlugin]] = {}
        
        # Periodic ticking list: [ (plugin_instance, tick_interval_sec, last_tick_timestamp) ]
        self.ticking_plugins: List[Tuple[BasePlugin, float, float]] = []

    def discover_and_load(self) -> Dict[str, BasePlugin]:
        """
        Scan the plugins directory, parse manifests, load classes, and invoke on_load().
        """
        if not os.path.exists(self.plugins_dir):
            self.logger.warning(f"Plugins directory not found: {self.plugins_dir}. Creating it...")
            os.makedirs(self.plugins_dir, exist_ok=True)
            return self.plugins

        self.logger.info(f"Scanning for plugins in: {self.plugins_dir}")

        for entry in os.listdir(self.plugins_dir):
            plugin_path = os.path.join(self.plugins_dir, entry)
            if os.path.isdir(plugin_path) and not entry.startswith((".", "_")):
                self._load_plugin_folder(plugin_path)

        self.logger.info(f"Successfully loaded {len(self.plugins)} plugin(s).")
        return self.plugins

    def _load_plugin_folder(self, folder_path: str) -> Optional[BasePlugin]:
        folder_name = os.path.basename(folder_path)
        manifest_file = os.path.join(folder_path, "manifest.yaml")
        manifest_data: Dict[str, Any] = {}

        # 1. Parse manifest.yaml if present
        if os.path.exists(manifest_file):
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    manifest_data = yaml.safe_load(f) or {}
            except Exception as e:
                self.logger.error(f"Failed to parse manifest.yaml in '{folder_name}': {e}")
                return None

        # 2. Find Python source files in the plugin directory
        py_files = [
            f for f in os.listdir(folder_path)
            if f.endswith(".py") and not f.startswith((".", "_"))
        ]
        
        if not py_files:
            self.logger.warning(f"No Python files found in plugin folder '{folder_name}'.")
            return None

        # Prioritize plugin.py or __init__.py if available
        entry_file = "plugin.py" if "plugin.py" in py_files else ("__init__.py" if "__init__.py" in py_files else py_files[0])
        entry_path = os.path.join(folder_path, entry_file)

        # 3. Dynamically import the plugin module
        module_name = f"desktop_pet_plugin_{folder_name}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, entry_path)
            if spec is None or spec.loader is None:
                self.logger.error(f"Could not load module spec for '{entry_path}'")
                return None
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        except Exception as e:
            self.logger.error(f"Error importing plugin '{folder_name}': {e}", exc_info=True)
            return None

        # 4. Find the BasePlugin subclass
        plugin_class = None
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, BasePlugin) and obj is not BasePlugin:
                plugin_class = obj
                break

        if plugin_class is None:
            self.logger.warning(f"No BasePlugin subclass found in '{entry_path}'.")
            return None

        # 5. Instantiate the plugin
        try:
            plugin_instance = plugin_class()
        except Exception as e:
            self.logger.error(f"Failed to instantiate plugin class '{plugin_class.__name__}': {e}")
            return None

        # 6. Resolve manifest
        manifest = plugin_instance.get_manifest()
        if not isinstance(manifest, PluginManifest):
            self.logger.error(f"Plugin '{plugin_class.__name__}' get_manifest() did not return a PluginManifest instance.")
            return None

        # Merge manifest.yaml overrides if defined
        if manifest_data:
            manifest.name = manifest_data.get("name", manifest.name)
            manifest.version = manifest_data.get("version", manifest.version)
            manifest.author = manifest_data.get("author", manifest.author)
            manifest.description = manifest_data.get("description", manifest.description)
            manifest.subscriptions = manifest_data.get("subscriptions", manifest.subscriptions)
            manifest.tick_interval = manifest_data.get("tick_interval", manifest.tick_interval)
            manifest.required_capabilities = manifest_data.get("required_capabilities", manifest.required_capabilities)

        plugin_name = manifest.name or folder_name

        # 7. Initialize with PluginContext
        try:
            # Provide a plugin-scoped logger
            scoped_logger = logging.getLogger(f"Plugin:{plugin_name}")
            plugin_ctx = PluginContext(
                ipc=self.context.ipc,
                emotion_engine=self.context.emotion_engine,
                ai=self.context.ai,
                stt=self.context.stt,
                config=self.context.config.get(plugin_name, {}),
                logger=scoped_logger,
                state=self.context.state.setdefault(plugin_name, {})
            )
            plugin_instance.on_load(plugin_ctx)
        except Exception as e:
            self.logger.error(f"Error during on_load for plugin '{plugin_name}': {e}", exc_info=True)
            return None

        # 8. Register subscriptions and ticking
        self.plugins[plugin_name] = plugin_instance

        for sub in manifest.subscriptions:
            self.subscriptions.setdefault(sub, []).append(plugin_instance)

        if manifest.tick_interval and manifest.tick_interval > 0:
            self.ticking_plugins.append((plugin_instance, manifest.tick_interval, time.time()))

        self.logger.info(
            f"  [+] Loaded '{plugin_name}' v{manifest.version} "
            f"(Subscriptions: {manifest.subscriptions}, Tick: {manifest.tick_interval}s)"
        )
        return plugin_instance

    def dispatch_event(self, event: IncomingEvent) -> None:
        """
        Route an incoming event only to plugins that declared an interest in it.
        Isolates plugin execution so an error in one plugin does not impact others.
        """
        target_patterns: Set[str] = {"*", event.event_type}

        # Specific sub-event patterns
        if event.event_type == "input_event" and event.hotkey_id:
            target_patterns.add(f"hotkey:{event.hotkey_id}")

        if event.is_clap:
            target_patterns.add("clap")

        # Collect unique target plugins
        recipients: Set[BasePlugin] = set()
        for pattern in target_patterns:
            if pattern in self.subscriptions:
                for plugin in self.subscriptions[pattern]:
                    recipients.add(plugin)

        # Dispatch event safely
        for plugin in recipients:
            try:
                plugin.on_event(event)
            except Exception as e:
                manifest = plugin.get_manifest()
                self.logger.error(f"Error in plugin '{manifest.name}' on_event(): {e}", exc_info=True)

    def tick(self, dt: float) -> None:
        """
        Trigger on_tick for all plugins that registered a tick_interval.
        """
        now = time.time()
        for i, (plugin, interval, last_tick) in enumerate(self.ticking_plugins):
            elapsed = now - last_tick
            if elapsed >= interval:
                self.ticking_plugins[i] = (plugin, interval, now)
                try:
                    plugin.on_tick(elapsed)
                except Exception as e:
                    manifest = plugin.get_manifest()
                    self.logger.error(f"Error in plugin '{manifest.name}' on_tick(): {e}", exc_info=True)

    def unload_all(self) -> None:
        """
        Gracefully tear down all loaded plugins on shutdown.
        """
        self.logger.info("Unloading all plugins...")
        for name, plugin in self.plugins.items():
            try:
                plugin.on_unload()
            except Exception as e:
                self.logger.error(f"Error during on_unload for plugin '{name}': {e}")

        self.plugins.clear()
        self.subscriptions.clear()
        self.ticking_plugins.clear()
