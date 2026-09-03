import os
import glob
import shlex
import shutil
import subprocess
import datetime
import urllib.parse
import re
import difflib
from typing import Optional, Tuple, Dict, Any, List
import psutil

from core.base_plugin import BasePlugin, PluginManifest, PluginContext, IncomingEvent


class OSNavigationPlugin(BasePlugin):
    """
    Advanced OS Navigation, Dynamic Desktop Application Launcher & System Automation Plugin:
    1. STRICT APP LAUNCHING: Always opens native desktop applications (Spotify, Discord, Steam, WhatsApp, Chrome, etc.), NEVER opening web browser for app requests.
    2. STRICT COMMAND EXECUTION: Automatically detects shell commands (e.g. 'run cargo build', 'run python main.py', 'run ls', 'in terminal run htop') and executes them in an interactive terminal window.
    3. COMPOUND URL ACTIONS: Detects requests to open a URL/site and perform actions on it (e.g. 'open youtube.com and search for lofi hip hop', 'open github.com and search for whisper').
    4. DIRECT URL / BROWSING: Opens explicit URLs/domains in the browser.
    5. DIRECTORY NAVIGATION: Opens folders in Terminal, VS Code, or File Manager.
    6. HARDWARE TELEMETRY: Live SSD disk space, RAM, CPU, Battery %, Time & Date.
    7. MEDIA & VOLUME CONTROL: Play/pause, track skipping, volume up/down/mute.
    """

    WORKSPACE_DIR = "/mnt/windows/Shourya_Personal_Files/Python_Directories/Python_Projects/desktop-pet"

    BUILTIN_ALIASES = {
        "browser": ["google-chrome-stable", "brave", "firefox", "chromium"],
        "web browser": ["google-chrome-stable", "brave", "firefox"],
        "terminal": ["kitty", "konsole", "alacritty", "foot", "wezterm", "gnome-terminal"],
        "kitty": ["kitty"],
        "konsole": ["konsole"],
        "code": ["codium", "vscodium", "code", "cursor"],
        "vs code": ["codium", "vscodium", "code", "cursor"],
        "vscode": ["codium", "vscodium", "code", "cursor"],
        "editor": ["codium", "vscodium", "code", "cursor", "kate", "gedit"],
        "files": ["dolphin", "thunar", "nautilus", "pcmanfm"],
        "file manager": ["dolphin", "thunar", "nautilus", "pcmanfm"],
        "task manager": ["kitty -e btop", "kitty -e htop", "konsole -e btop"],
        "music": ["spotify", "spotify-launcher"],
        "spotify": ["spotify", "spotify-launcher"],
        "discord": ["discord", "webcord", "vesktop"],
        "steam": ["steam"],
        "chrome": ["google-chrome-stable", "google-chrome"],
        "google chrome": ["google-chrome-stable", "google-chrome"],
        "brave": ["brave"],
        "firefox": ["firefox"],
        "telegram": ["telegram-desktop"],
        "whatsapp": ["whatsapp-for-linux", "whatsapp-desktop", "walc"],
        "vlc": ["vlc"],
        "mpv": ["mpv"],
        "settings": ["systemsettings", "gnome-control-center"],
    }

    CLI_TOOLS = {
        "htop", "btop", "top", "vim", "nvim", "nano", "neofetch", "fastfetch",
        "cmatrix", "ranger", "yazi", "ncdu", "lazygit", "gitui", "cargo", "python",
        "python3", "rustc", "npm", "node", "git", "ls", "ps", "kill", "grep"
    }

    def get_manifest(self) -> PluginManifest:
        return PluginManifest(
            name="OSNavigation",
            version="1.2.0",
            description="Strict native application launcher, terminal command runner, compound URL action engine, and system telemetry.",
            subscriptions=["hotkey:os_action", "os_command"],
            tick_interval=None,
        )

    def _index_windows_applications(self) -> None:
        """Index Windows Start Menu programs and standard Win32 applications."""
        win_builtins = {
            "notepad": "notepad.exe",
            "calculator": "calc.exe",
            "calc": "calc.exe",
            "explorer": "explorer.exe",
            "file manager": "explorer.exe",
            "files": "explorer.exe",
            "task manager": "taskmgr.exe",
            "taskmgr": "taskmgr.exe",
            "cmd": "cmd.exe",
            "powershell": "powershell.exe",
            "terminal": "wt.exe",
            "windows terminal": "wt.exe",
            "paint": "mspaint.exe",
            "settings": "ms-settings:",
            "chrome": "chrome.exe",
            "google chrome": "chrome.exe",
            "edge": "msedge.exe",
            "microsoft edge": "msedge.exe",
            "spotify": "spotify.exe",
            "discord": "discord.exe",
            "steam": "steam.exe",
            "vscode": "code.exe",
            "code": "code.exe",
        }
        for name, cmd in win_builtins.items():
            self.app_index[name] = {
                "display_name": name.capitalize(),
                "exec_cmd": cmd,
                "desktop_id": name,
                "is_terminal": False,
                "is_windows": True,
            }

        start_menu_dirs = [
            os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
        ]
        for sm_dir in start_menu_dirs:
            if os.path.exists(sm_dir):
                for root, _, files in os.walk(sm_dir):
                    for f in files:
                        if f.lower().endswith((".lnk", ".url", ".exe")):
                            app_name = os.path.splitext(f)[0].lower()
                            full_p = os.path.join(root, f)
                            self.app_index[app_name] = {
                                "display_name": os.path.splitext(f)[0],
                                "exec_cmd": full_p,
                                "desktop_id": app_name,
                                "is_terminal": False,
                                "is_windows": True,
                            }

    def on_load(self, context: PluginContext) -> None:
        self.ctx = context
        self.app_index: Dict[str, Dict[str, Any]] = {}
        self._index_installed_applications()
        self.ctx.logger.info(f"OSNavigationPlugin loaded! Indexed {len(self.app_index)} native desktop application triggers.")

    def _index_installed_applications(self) -> None:
        """Scan system directories and index all installed applications (Linux XDG & Windows Start Menu)."""
        if sys.platform == "win32":
            self._index_windows_applications()
            return

        desktop_dirs = [
            "/usr/share/applications",
            "/usr/local/share/applications",
            os.path.expanduser("~/.local/share/applications"),
            "/var/lib/flatpak/exports/share/applications",
            os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
            "/var/lib/snapd/desktop/applications",
        ]

        xdg_dirs = os.environ.get("XDG_DATA_DIRS", "").split(":")
        for xd in xdg_dirs:
            if xd:
                app_path = os.path.join(xd, "applications")
                if app_path not in desktop_dirs:
                    desktop_dirs.append(app_path)

        for d in desktop_dirs:
            if not os.path.exists(d):
                continue
            desktop_files = glob.glob(os.path.join(d, "*.desktop")) + glob.glob(os.path.join(d, "**/*.desktop"))
            for f in desktop_files:
                try:
                    with open(f, "r", encoding="utf-8", errors="ignore") as fp:
                        lines = fp.readlines()

                    name = ""
                    exec_cmd = ""
                    nodisplay = False
                    generic = ""
                    is_terminal = False
                    keywords = []

                    in_main_section = False
                    for line in lines:
                        line = line.strip()
                        if line == "[Desktop Entry]":
                            in_main_section = True
                            continue
                        elif line.startswith("[") and line.endswith("]"):
                            in_main_section = False
                            continue

                        if in_main_section and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip()
                            if k == "Name" and not name:
                                name = v
                            elif k == "GenericName" and not generic:
                                generic = v
                            elif k == "Exec" and not exec_cmd:
                                exec_cmd = v
                            elif k == "NoDisplay" and v.lower() == "true":
                                nodisplay = True
                            elif k == "Terminal" and v.lower() == "true":
                                is_terminal = True
                            elif k == "Keywords":
                                keywords = [kw.strip().lower() for kw in v.split(";") if kw.strip()]

                    if name and exec_cmd and not nodisplay:
                        clean_exec = re.sub(r"%[a-zA-Z]", "", exec_cmd).strip()
                        desktop_id = os.path.basename(f).replace(".desktop", "")

                        entry = {
                            "display_name": name,
                            "exec_cmd": clean_exec,
                            "desktop_id": desktop_id,
                            "desktop_file": f,
                            "is_terminal": is_terminal,
                        }

                        self.app_index[name.lower()] = entry
                        self.app_index[desktop_id.lower()] = entry
                        if generic:
                            self.app_index[generic.lower()] = entry
                        for kw in keywords:
                            if len(kw) > 2 and kw not in self.app_index:
                                self.app_index[kw] = entry

                except Exception:
                    pass

    def on_event(self, event: IncomingEvent) -> None:
        if event.data and "query" in event.data:
            query = event.data["query"]
            handled, reply, emotion = self.handle_query(query)
            if handled:
                self.ctx.send_emotion(emotion, priority=130, duration=10.0)
                self.ctx.send_speech(reply)

    def resolve_directory(self, raw_path: str) -> str:
        """Resolve friendly directory aliases to absolute paths."""
        text = raw_path.strip().lower()
        if any(w in text for w in ["pet-brain", "pet brain", "brain"]):
            return os.path.join(self.WORKSPACE_DIR, "pet-brain")
        if any(w in text for w in ["pet-shell", "pet shell", "shell"]):
            return os.path.join(self.WORKSPACE_DIR, "pet-shell")
        if any(w in text for w in ["project", "workspace", "desktop pet", "here", "this"]):
            return self.WORKSPACE_DIR
        if "download" in text:
            return os.path.expanduser("~/Downloads")
        if "document" in text:
            return os.path.expanduser("~/Documents")
        if "picture" in text or "photo" in text:
            return os.path.expanduser("~/Pictures")
        if "music" in text:
            return os.path.expanduser("~/Music")
        if "video" in text:
            return os.path.expanduser("~/Videos")
        if "home" in text:
            return os.path.expanduser("~")

        expanded = os.path.expanduser(raw_path.strip())
        if os.path.exists(expanded):
            return os.path.abspath(expanded)
        return self.WORKSPACE_DIR

    def handle_query(self, query: str) -> Tuple[bool, str, str]:
        """
        Parse natural language intent and execute system / web / browsing / terminal action.
        Returns (handled, reply_text, emotion_name).
        """
        text = query.strip().lower()
        # Remove trailing and leading punctuation (. , ! ? :)
        text = re.sub(r"[.,!?:;]+$", "", text).strip()
        # Strip conversational filler prefixes/suffixes ('can you', 'could you', 'please', 'for me')
        text = re.sub(r"^(?:can you\s+|could you\s+|please\s+|zoro\s+)", "", text).strip()
        text = re.sub(r"\s+(?:for me|for us|please|now|zoro)$", "", text).strip()

        # Pass-through: If the user is asking to read/describe screen or code, let vision/LLM handle it
        if any(k in text for k in ["on my screen", "read my screen", "read the screen", "describe my screen", "look at my screen", "what code is", "explain this code", "read this code", "tell me what is on", "what is on my screen", "what is opened on my screen"]):
            return False, "", "idle"

        # -------------------------------------------------------------
        # 1. HARDWARE & SYSTEM TELEMETRY
        # -------------------------------------------------------------
        # Combined RAM & Disk & Full System Info
        if any(k in text for k in [
            "ram and disk", "disk and ram", "system info", "system information", "system stats",
            "hardware stats", "hardware info", "pc stats", "pc info", "computer stats", "system status",
            "full system", "all stats"
        ]):
            stats = self.get_system_stats()
            cpu = stats.get("cpu_percent", 0)
            ram_pct = stats.get("ram_percent", 0)
            ram_used_gb = stats.get("ram_used_gb", 0)
            ram_total_gb = stats.get("ram_total_gb", 0)
            disk_free = stats.get("disk_free_gb", 0)
            disk_total = stats.get("disk_total_gb", 0)
            disk_used = stats.get("disk_used_gb", 0)
            disk_pct = stats.get("disk_percent", 0)
            return True, f"RAM: {ram_pct}% ({ram_used_gb:.1f}/{ram_total_gb:.1f} GB) | Disk: {disk_pct}% ({disk_free:.1f} GB free/{disk_total:.1f} GB) | CPU: {cpu}% 🚀", "proud"

        # RAM & CPU / Memory
        if any(k in text for k in [
            "ram", "memory", "cpu", "how much ram", "ram do i have", "memory usage", "check ram",
            "check cpu", "cpu usage", "ram usage", "my ram", "how much memory", "memory is used",
            "ram is used", "tell my ram", "check memory"
        ]):
            stats = self.get_system_stats()
            cpu = stats.get("cpu_percent", 0)
            ram_pct = stats.get("ram_percent", 0)
            ram_used_gb = stats.get("ram_used_gb", 0)
            ram_total_gb = stats.get("ram_total_gb", 0)
            return True, f"RAM: {ram_pct}% ({ram_used_gb:.1f}/{ram_total_gb:.1f} GB) | CPU: {cpu}% 🚀", "proud"

        # SSD / Disk space & Storage
        if any(k in text for k in [
            "disk", "storage", "ssd", "hard drive", "free space", "disk space", "disk storage",
            "ssd storage", "ssd space", "disk usage", "how much storage", "how much disk",
            "storage do i have", "disk do i have", "storage usage", "drive space", "drive storage",
            "my disk", "my storage", "tell my disk"
        ]):
            stats = self.get_system_stats()
            disk_free = stats.get("disk_free_gb", 0)
            disk_total = stats.get("disk_total_gb", 0)
            disk_used = stats.get("disk_used_gb", 0)
            disk_pct = stats.get("disk_percent", 0)
            return True, f"Disk: {disk_pct}% used ({disk_free:.1f} GB free out of {disk_total:.1f} GB, {disk_used:.1f} GB used)! 💾✨", "proud"

        # Battery & Power
        if any(k in text for k in ["battery", "power", "charging", "battery status", "battery percentage", "battery level", "power level", "my battery", "tell battery"]):
            stats = self.get_system_stats()
            batt = stats.get("battery")
            if batt is not None:
                charging = "⚡ Charging" if stats.get("power_plugged") else "🔋 Discharging"
                return True, f"Battery: {int(batt)}% ({charging})! ✨", "happy" if batt > 30 else "startled"
            return True, "No battery detected (desktop system connected to AC power). 🔌", "idle"

        # Current Time & Date
        if any(k in text for k in ["what time is it", "tell me time", "current time", "what date is it", "today date", "what day is it", "what's the time"]):
            now = datetime.datetime.now()
            time_str = now.strftime("%I:%M %p")
            date_str = now.strftime("%A, %B %d, %Y")
            return True, f"It's {time_str} on {date_str}! ⏰✨", "happy"

        # -------------------------------------------------------------
        # 2. MEDIA PLAYBACK & VOLUME CONTROL
        # -------------------------------------------------------------
        if any(k in text for k in ["pause music", "pause song", "stop music", "pause playback"]):
            success = self.control_media("pause")
            return True, "Paused playback for you! ⏸️" if success else "No active media player found to pause.", "idle"

        if any(k in text for k in ["play music", "resume music", "resume song", "play song", "unpause"]):
            success = self.control_media("play")
            return True, "Resumed your music! ▶️ 🎵" if success else "No media player open to resume.", "happy"

        if any(k in text for k in ["next song", "next track", "skip song", "skip track"]):
            success = self.control_media("next")
            track = self.get_current_track()
            msg = f"Skipped to next track! ⏭️ ({track})" if track else "Skipped to next track! ⏭️"
            return True, msg, "happy"

        if any(k in text for k in ["previous song", "previous track", "prev song", "last song"]):
            success = self.control_media("previous")
            return True, "Went back to the previous track! ⏮️" if success else "Could not go to previous track.", "happy"

        if any(k in text for k in ["mute volume", "mute audio", "silence audio", "mute sound", "mute"]):
            self.control_volume("mute")
            return True, "Muted system audio! 🔇", "idle"

        if any(k in text for k in ["unmute", "enable sound", "unmute audio"]):
            self.control_volume("unmute")
            return True, "Unmuted audio! 🔊", "happy"

        if any(k in text for k in ["volume up", "louder", "turn up volume", "increase volume"]):
            self.control_volume("up", 10)
            return True, "Turned up the volume! 🔊", "happy"

        if any(k in text for k in ["volume down", "quieter", "lower volume", "decrease volume", "turn down volume"]):
            self.control_volume("down", 10)
            return True, "Lowered the volume! 🔉", "idle"

        if any(k in text for k in ["lock screen", "lock computer", "lock pc", "lock desktop"]):
            success = self.lock_screen()
            return True, "Locking your screen now! See you soon! 🔒" if success else "Lock command not available.", "idle"

        # -------------------------------------------------------------
        # 3. COMPOUND URL + ACTION ON URL
        # E.g. "open youtube.com and search for lofi hip hop"
        #      "open github.com and search for whisper"
        #      "open google.com and search for rust tutorials"
        # -------------------------------------------------------------
        compound_match = re.search(r"^(?:open|go\s*to|browse\s*to)\s+(?:the\s+)?([a-z0-9\.\-_]+)\s+and\s+(?:search\s*(?:for)?|play|find|look\s*for|browse)\s+(.+)$", text)
        if compound_match:
            site_target = compound_match.group(1).strip()
            action_query = compound_match.group(2).strip()

            # Determine engine from site target
            engine = "google"
            if "youtube" in site_target:
                engine = "youtube"
            elif "github" in site_target:
                engine = "github"
            elif "reddit" in site_target:
                engine = "reddit"
            elif "wiki" in site_target:
                engine = "arch wiki"

            opened, url = self.search_web(action_query, engine)
            if opened:
                return True, f"Opened {site_target} and searched for '{action_query}'! 🌐✨", "happy"

        # -------------------------------------------------------------
        # 4. DIRECT WEB SEARCH (Google, YouTube, GitHub, ArchWiki)
        # E.g. "search google for rust tutorials", "search youtube for lofi"
        # -------------------------------------------------------------
        search_match = re.search(r"^(?:search|look\s*up|find|browse)\s+(?:on\s+)?(google|youtube|github|arch\s*wiki|wiki|web)?\s*(?:for\s+)?(.+)$", text)
        if search_match:
            engine = (search_match.group(1) or "google").strip().replace(" ", "")
            search_term = search_match.group(2).strip()
            opened, url = self.search_web(search_term, engine)
            if opened:
                return True, f"Searching {engine.capitalize()} for '{search_term}'! 🌐✨", "happy"

        if text.startswith("google ") or text.startswith("search for "):
            term = text.split(" ", 1)[1].strip()
            opened, _ = self.search_web(term, "google")
            if opened:
                return True, f"Googling '{term}' for you! 🔍✨", "happy"

        if text.startswith("youtube ") or text.startswith("play on youtube ") or text.startswith("search youtube for "):
            term = text.replace("search youtube for", "").replace("play on youtube", "").replace("youtube", "").strip()
            opened, _ = self.search_web(term, "youtube")
            if opened:
                return True, f"Searching YouTube for '{term}'! 📺🎵", "happy"

        # -------------------------------------------------------------
        # 5. DIRECT URL / DOMAIN OPENING
        # E.g. "open youtube.com", "open github.com", "open url https://...", "browse to reddit.com"
        # -------------------------------------------------------------
        if text.startswith(("open url ", "open website ", "browse to ", "go to ")):
            for prefix in ["open url ", "open website ", "browse to ", "go to "]:
                if text.startswith(prefix):
                    target = text[len(prefix):].strip()
                    url = target if target.startswith("http") else f"https://{target}"
                    if self.open_url(url):
                        return True, f"Opening {target}! 🌐✨", "happy"

        if text.startswith("open "):
            target = text[5:].strip()
            # If target has a web TLD (e.g. youtube.com, github.com, reddit.com, example.org)
            if re.search(r"\.(?:com|org|io|net|edu|gov|co|in|ai|dev|app|xyz)(?:/.*)?$", target) or target.startswith(("http://", "https://")):
                url = target if target.startswith("http") else f"https://{target}"
                if self.open_url(url):
                    return True, f"Opening {target}! 🌐✨", "happy"

        # -------------------------------------------------------------
        # 6. EXPLICIT COMMAND EXECUTION
        # E.g. "run cargo build", "run python main.py", "run git status", "execute ls", "in terminal run htop"
        # -------------------------------------------------------------
        cmd_to_run = None
        for prefix in ["run command ", "execute ", "in terminal run ", "open terminal and run "]:
            if text.startswith(prefix):
                cmd_to_run = text[len(prefix):].strip()
                break

        if not cmd_to_run and text.startswith("run "):
            candidate_cmd = text[4:].strip()
            bin_head = candidate_cmd.split()[0]
            if len(candidate_cmd.split()) > 1 or bin_head in self.CLI_TOOLS:
                cmd_to_run = candidate_cmd

        if cmd_to_run:
            launched, t_name = self.run_terminal_command(cmd_to_run)
            if launched:
                return True, f"Running '{cmd_to_run}' in {t_name}! 💻🚀", "happy"

        # -------------------------------------------------------------
        # 7. DIRECTORY NAVIGATION IN TERMINAL / CODE / FILE MANAGER
        # E.g. "open terminal in project", "open code in pet-brain"
        # -------------------------------------------------------------
        if "terminal" in text and any(w in text for w in ["in ", "here", "path", "project", "workspace", "brain", "shell", "downloads", "documents", "folder"]):
            dir_target = text.replace("open", "").replace("terminal", "").replace("in", "").replace("directory", "").replace("folder", "").strip()
            resolved_path = self.resolve_directory(dir_target)
            launched, t_name = self.open_terminal(resolved_path)
            if launched:
                folder_name = os.path.basename(resolved_path) or resolved_path
                return True, f"Opened {t_name} in '{folder_name}'! 💻🚀", "happy"

        if any(w in text for w in ["code", "editor", "vs code", "codium"]) and any(w in text for w in ["in project", "in folder", "in directory", "in workspace", "here"]):
            dir_target = text.replace("open", "").replace("code", "").replace("editor", "").replace("vs", "").replace("in", "").strip()
            resolved_path = self.resolve_directory(dir_target)
            self.launch_app(f"code {resolved_path}")
            folder_name = os.path.basename(resolved_path) or resolved_path
            return True, f"Opened '{folder_name}' in Code editor! 📝✨", "happy"

        if any(w in text for w in ["files", "file manager", "file explorer"]) and any(w in text for w in ["in project", "in folder", "in directory", "in downloads", "in documents"]):
            dir_target = text.replace("open", "").replace("files", "").replace("file manager", "").replace("in", "").strip()
            resolved_path = self.resolve_directory(dir_target)
            self.launch_app(f"dolphin {resolved_path}")
            folder_name = os.path.basename(resolved_path) or resolved_path
            return True, f"Opened folder '{folder_name}' in file manager! 📂✨", "happy"

        # -------------------------------------------------------------
        # 8. STRICT NATIVE APPLICATION LAUNCHING
        # E.g. "open spotify", "open discord", "open steam", "open chrome", "open brave", "open terminal", "open file manager"
        # MUST open the native application, NEVER the web browser!
        # -------------------------------------------------------------
        app_match = re.match(r"^(?:open|launch|start|run)\s+(?:the\s+)?(?:app\s+|application\s+)?([a-z0-9\-_ ]+)$", text)
        if app_match:
            app_req = app_match.group(1).strip()
            app_req = re.sub(r"\s+(?:app|application)$", "", app_req).strip()
            launched, actual_name = self.launch_app(app_req)
            if launched:
                return True, f"Opening {actual_name} for you! 🚀✨", "happy"

        return False, "", "idle"

    def run_terminal_command(self, cmd: str) -> Tuple[bool, str]:
        """Execute a command in a new visible terminal window (cross-platform)."""
        if sys.platform == "win32":
            if shutil.which("wt"):
                try:
                    subprocess.Popen(["wt.exe", "cmd.exe", "/k", cmd], start_new_session=True)
                    return True, "Windows Terminal"
                except Exception:
                    pass
            try:
                subprocess.Popen(["cmd.exe", "/k", cmd], start_new_session=True)
                return True, "Command Prompt"
            except Exception:
                return False, "Terminal" 
        # Kitty
        if shutil.which("kitty"):
            try:
                subprocess.Popen(["kitty", "-e", "bash", "-c", f"{cmd}; exec bash"], start_new_session=True)
                return True, "Kitty Terminal"
            except Exception:
                pass

        # Konsole
        if shutil.which("konsole"):
            try:
                subprocess.Popen(["konsole", "-e", "bash", "-c", f"{cmd}; exec bash"], start_new_session=True)
                return True, "Konsole Terminal"
            except Exception:
                pass

        return False, "Terminal"

    def open_url(self, url: str) -> bool:
        """Open a website URL in the user's default browser."""
        try:
            import webbrowser
            if sys.platform == "win32":
                webbrowser.open(url)
                return True
            for browser in ["google-chrome-stable", "google-chrome", "brave", "firefox", "xdg-open"]:
                if shutil.which(browser):
                    subprocess.Popen([browser, url], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    self.ctx.logger.info(f"Opened URL via {browser}: {url}")
                    return True
            webbrowser.open(url)
            return True
        except Exception as e:
            self.ctx.logger.warning(f"Failed to open URL {url}: {e}")
        return False

    def search_web(self, query: str, engine: str = "google") -> Tuple[bool, str]:
        """Perform a web search on Google, YouTube, GitHub, Reddit, or ArchWiki."""
        encoded = urllib.parse.quote_plus(query.strip())
        engine_lower = engine.lower()

        if "youtube" in engine_lower:
            url = f"https://www.youtube.com/results?search_query={encoded}"
        elif "github" in engine_lower:
            url = f"https://github.com/search?q={encoded}"
        elif "reddit" in engine_lower:
            url = f"https://www.reddit.com/search/?q={encoded}"
        elif "arch" in engine_lower or "wiki" in engine_lower:
            url = f"https://wiki.archlinux.org/index.php?search={encoded}"
        else:
            url = f"https://www.google.com/search?q={encoded}"

        opened = self.open_url(url)
        return opened, url

    def open_terminal(self, directory: Optional[str] = None) -> Tuple[bool, str]:
        """Launch terminal at a specific directory path."""
        target_dir = directory or self.WORKSPACE_DIR
        target_dir = os.path.abspath(os.path.expanduser(target_dir))

        if not os.path.exists(target_dir):
            target_dir = self.WORKSPACE_DIR

        # Kitty
        if shutil.which("kitty"):
            try:
                subprocess.Popen(["kitty", "--directory", target_dir], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.ctx.logger.info(f"Launched Kitty in: {target_dir}")
                return True, "Kitty Terminal"
            except Exception as e:
                self.ctx.logger.warning(f"Kitty launch failed: {e}")

        # Konsole
        if shutil.which("konsole"):
            try:
                subprocess.Popen(["konsole", "--workdir", target_dir], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.ctx.logger.info(f"Launched Konsole in: {target_dir}")
                return True, "Konsole Terminal"
            except Exception as e:
                self.ctx.logger.warning(f"Konsole launch failed: {e}")

        # Fallback terminal
        return self.launch_app("terminal")

    def launch_app(self, name: str) -> Tuple[bool, str]:
        """
        Universal Multi-Strategy Application Launcher:
        Always launches native desktop applications, never opens browser!
        1. Builtin Alias lookup
        2. Dynamic Linux Desktop Index exact match
        3. Dynamic Linux Desktop Index fuzzy / substring match
        4. CLI terminal wrap (if binary is a terminal tool)
        5. Direct binary execution via PATH
        """
        name_clean = name.strip().lower()

        # Strategy 1: Check Builtin Aliases
        if name_clean in self.BUILTIN_ALIASES:
            for candidate in self.BUILTIN_ALIASES[name_clean]:
                bin_name = candidate.split()[0]
                if shutil.which(bin_name):
                    try:
                        args = shlex.split(candidate)
                        subprocess.Popen(args, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        self.ctx.logger.info(f"Launched builtin alias: {candidate}")
                        return True, name_clean.capitalize()
                    except Exception:
                        pass

        # Strategy 2: Exact Match in Dynamic Desktop Application Index
        if name_clean in self.app_index:
            entry = self.app_index[name_clean]
            if self._spawn_desktop_entry(entry):
                return True, entry["display_name"]

        # Strategy 3: Fuzzy / Substring Match in Dynamic Desktop Application Index
        for app_key, entry in self.app_index.items():
            if name_clean in app_key or app_key in name_clean:
                if self._spawn_desktop_entry(entry):
                    return True, entry["display_name"]

        matches = difflib.get_close_matches(name_clean, list(self.app_index.keys()), n=1, cutoff=0.6)
        if matches:
            entry = self.app_index[matches[0]]
            if self._spawn_desktop_entry(entry):
                return True, entry["display_name"]

        # Strategy 4: CLI tools (e.g. htop, btop, vim, nano) -> Wrap in terminal
        bin_base = name_clean.split()[0]
        if bin_base in self.CLI_TOOLS and shutil.which(bin_base):
            launched, t_name = self.run_terminal_command(name_clean)
            if launched:
                return True, f"{bin_base.capitalize()} in {t_name}"

        # Strategy 5: Direct PATH binary execution
        if shutil.which(bin_base):
            try:
                args = shlex.split(name_clean)
                subprocess.Popen(args, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.ctx.logger.info(f"Launched direct binary: {name_clean}")
                return True, bin_base.capitalize()
            except Exception as e:
                self.ctx.logger.warning(f"Failed direct binary launch for {name_clean}: {e}")

        return False, name

    def _spawn_desktop_entry(self, entry: Dict[str, Any]) -> bool:
        """Spawn a desktop application entry in a clean detached process."""
        exec_cmd = entry["exec_cmd"]
        is_terminal = entry.get("is_terminal", False)
        desktop_id = entry.get("desktop_id", "")

        if sys.platform == "win32" or entry.get("is_windows"):
            try:
                if hasattr(os, "startfile") and (exec_cmd.startswith("ms-") or os.path.exists(exec_cmd)):
                    os.startfile(exec_cmd)
                    return True
                subprocess.Popen(["cmd.exe", "/c", "start", "", exec_cmd], shell=True)
                return True
            except Exception as e:
                self.ctx.logger.warning(f"Windows app spawn failed for {exec_cmd}: {e}")
                return False

        # If it requires a terminal, run it inside Kitty / Konsole
        if is_terminal:
            launched, _ = self.run_terminal_command(exec_cmd)
            return launched

        # Try gtk-launch first if available
        if shutil.which("gtk-launch") and desktop_id:
            try:
                subprocess.Popen(["gtk-launch", desktop_id], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.ctx.logger.info(f"Spawned application via gtk-launch: {desktop_id}")
                return True
            except Exception:
                pass

        # Direct executable spawning
        try:
            args = shlex.split(exec_cmd)
            bin_name = args[0]
            if shutil.which(bin_name) or os.path.exists(bin_name):
                subprocess.Popen(args, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.ctx.logger.info(f"Spawned application: {exec_cmd}")
                return True
        except Exception as e:
            self.ctx.logger.warning(f"Failed to spawn {exec_cmd}: {e}")

        return False

    def control_media(self, action: str) -> bool:
        """Control media playback via playerctl."""
        if not shutil.which("playerctl"):
            return False
        try:
            res = subprocess.run(["playerctl", action], capture_output=True, timeout=2.0)
            return res.returncode == 0
        except Exception as e:
            self.ctx.logger.warning(f"Media control failed: {e}")
            return False

    def get_current_track(self) -> Optional[str]:
        """Get currently playing track title and artist via playerctl."""
        if not shutil.which("playerctl"):
            return None
        try:
            res = subprocess.run(
                ["playerctl", "metadata", "--format", "{{artist}} - {{title}}"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass
        return None

    def control_volume(self, action: str, step_pct: int = 5) -> bool:
        """Control system volume via wpctl or pactl."""
        try:
            if shutil.which("wpctl"):
                if action == "up":
                    subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{step_pct}%+"], timeout=2.0)
                elif action == "down":
                    subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{step_pct}%-"], timeout=2.0)
                elif action == "mute":
                    subprocess.run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "1"], timeout=2.0)
                elif action == "unmute":
                    subprocess.run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "0"], timeout=2.0)
                return True
            elif shutil.which("pactl"):
                if action == "up":
                    subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"+{step_pct}%"], timeout=2.0)
                elif action == "down":
                    subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"-{step_pct}%"], timeout=2.0)
                elif action == "mute":
                    subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "1"], timeout=2.0)
                elif action == "unmute":
                    subprocess.run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"], timeout=2.0)
                return True
        except Exception as e:
            self.ctx.logger.warning(f"Volume control failed: {e}")
        return False

    def get_system_stats(self) -> dict:
        """Query CPU, RAM, Battery, and Disk Storage metrics."""
        cpu = psutil.cpu_percent(interval=None)
        vm = psutil.virtual_memory()
        batt = psutil.sensors_battery()
        disk = psutil.disk_usage("/")

        return {
            "cpu_percent": cpu,
            "ram_percent": vm.percent,
            "ram_used_gb": vm.used / (1024 ** 3),
            "ram_total_gb": vm.total / (1024 ** 3),
            "battery": batt.percent if batt else None,
            "power_plugged": batt.power_plugged if batt else None,
            "disk_total_gb": disk.total / (1024 ** 3),
            "disk_free_gb": disk.free / (1024 ** 3),
            "disk_used_gb": disk.used / (1024 ** 3),
            "disk_percent": disk.percent,
        }

    def lock_screen(self) -> bool:
        """Lock the current desktop session (cross-platform)."""
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.user32.LockWorkStation()
                return True
            except Exception:
                try:
                    subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
                    return True
                except Exception:
                    return False

        for cmd in [["hyprlock"], ["swaylock"], ["loginctl", "lock-session"]]:
            if shutil.which(cmd[0]):
                try:
                    subprocess.Popen(cmd, start_new_session=True)
                    return True
                except Exception:
                    pass
        return False

    def on_unload(self) -> None:
        self.ctx.logger.info("OSNavigationPlugin unloaded.")
