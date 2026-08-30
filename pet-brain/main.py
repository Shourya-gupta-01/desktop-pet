import time
import pet_pb2
from core.ipc_server import IPCServer

def main():
    print("Starting Desktop Pet Brain...")
    
    # Initialize and bind the ZeroMQ server
    ipc = IPCServer()
    ipc.start()
    
    print("Brain is active. Waiting for events from the Shell...")
    
    try:
        while True:
            # Poll for incoming messages (blocking so we don't chew CPU)
            # In Phase 2 we just block. Later we'll use non-blocking with async plugins.
            msg = ipc.receive_message(blocking=True)
            
            if msg:
                # Which field inside the 'oneof' is populated?
                msg_type = msg.WhichOneof("message_type")
                print(f"[Brain] Received: {msg_type}")
                
                if msg_type == "input_event":
                    event = msg.input_event
                    print(f"        -> Hotkey: {event.hotkey_id}")
                    
                    # Whenever we receive any input event, send back a "happy" emotion command
                    # This proves the end-to-end bidirectional IPC loop works.
                    print("[Brain] Sending EmotionCommand('happy') response...")
                    response = pet_pb2.PetMessage()
                    response.emotion_command.emotion_id = "happy"
                    response.emotion_command.priority = 100
                    
                    ipc.send_message(response)
                    
    except KeyboardInterrupt:
        print("\nShutting down Brain...")

if __name__ == "__main__":
    main()
