import os
import sys
import time
import logging

import pet_pb2
from core.ipc_server import IPCServer
from core.base_plugin import PluginContext, IncomingEvent
from core.plugin_loader import PluginLoader
from core.ai_bridge import AIBridge
from core.emotion_engine import EmotionEngine
from core.stt_engine import STTEngine


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def main():
    setup_logging()
    logger = logging.getLogger("Brain")
    logger.info("Initializing Desktop Pet Brain...")

    # 1. Start the IPC Server (ZeroMQ PAIR socket)
    ipc = IPCServer()
    ipc.start()

    # 2. Initialize the Emotion Engine (16-state priority machine + decay timers)
    emotion_engine = EmotionEngine(ipc_server=ipc, default_emotion="idle")

    # 3. Initialize the AI Bridge (Ollama integration) and perform health-check
    ai_bridge = AIBridge()
    is_healthy, status_msg, available_models = ai_bridge.health_check()

    if not is_healthy:
        logger.warning(f"AI Service Notice: {status_msg}")
        # Send warning speech bubble to shell so user is notified visually
        warning_msg = pet_pb2.PetMessage()
        warning_msg.speech_bubble.text = f"Ollama not running: {status_msg}"
        warning_msg.speech_bubble.is_streaming_chunk = False
        try:
            ipc.send_message(warning_msg)
        except Exception:
            pass
    else:
        logger.info(f"AI Bridge ready! Available models: {available_models}")

    # 4. Initialize and pre-warm the Offline STT Engine (faster-whisper tiny.en)
    stt_engine = STTEngine(model_size="tiny.en")
    try:
        stt_engine._ensure_model_loaded()
        logger.info("STT Engine pre-warmed and ready for instant voice response!")
    except Exception as e:
        logger.warning(f"Could not pre-warm STT engine: {e}")

    # 5. Build the shared Plugin Context with EmotionEngine, AI, and STT access
    context = PluginContext(
        ipc=ipc,
        emotion_engine=emotion_engine,
        ai=ai_bridge if is_healthy else None,
        stt=stt_engine,
        config={},
        logger=logging.getLogger("PluginSystem"),
    )

    # 5. Discover and load all plugins in pet-brain/plugins/
    base_dir = os.path.dirname(os.path.abspath(__file__))
    plugins_dir = os.path.join(base_dir, "plugins")
    loader = PluginLoader(plugins_dir=plugins_dir, context=context)
    loader.discover_and_load()

    logger.info("Desktop Pet Brain is active and routing events!")

    last_time = time.time()

    try:
        while True:
            # 1. Calculate delta time for periodic plugin ticks & emotion decay
            current_time = time.time()
            dt = current_time - last_time
            last_time = current_time

            # 2. Non-blocking IPC message polling
            msg = ipc.receive_message(blocking=False)
            if msg:
                msg_type = msg.WhichOneof("message_type")
                
                # Normalize raw Protobuf into a typed IncomingEvent
                event_data = {}
                if msg_type == "input_event":
                    event_data = {
                        "hotkey_id": msg.input_event.hotkey_id,
                        "timestamp": msg.input_event.timestamp,
                    }
                elif msg_type == "audio_event":
                    event_data = {
                        "amplitude": msg.audio_event.amplitude,
                        "is_clap": msg.audio_event.is_clap,
                    }
                elif msg_type == "screen_frame":
                    event_data = {
                        "jpeg_bytes": msg.screen_frame.jpeg_bytes,
                        "width": msg.screen_frame.width,
                        "height": msg.screen_frame.height,
                        "timestamp": msg.screen_frame.timestamp,
                    }

                incoming_event = IncomingEvent(
                    event_type=msg_type or "unknown",
                    raw_message=msg,
                    data=event_data,
                    timestamp=time.time(),
                )

                # Dispatch to all subscribed plugins
                loader.dispatch_event(incoming_event)

            # 3. Fire periodic ticks for plugins and emotion decay timers
            loader.tick(dt)
            emotion_engine.tick(dt)

            # 4. Small sleep to avoid pegged CPU spin while remaining low-latency (10ms)
            time.sleep(0.01)

    except KeyboardInterrupt:
        logger.info("Shutdown requested. Cleaning up...")
    finally:
        loader.unload_all()
        ai_bridge.shutdown()
        logger.info("Desktop Pet Brain shutdown complete.")


if __name__ == "__main__":
    main()
