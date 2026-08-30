import time
import zmq
import pet_pb2

def main():
    context = zmq.Context()
    # Python acts as the server (binds) for this test, Rust connects
    socket = context.socket(zmq.PAIR)
    socket.bind("tcp://127.0.0.1:5555")
    print("[Python] Bound to tcp://127.0.0.1:5555. Waiting for Rust...")

    # 1. Receive InputEvent from Rust
    msg_bytes = socket.recv()
    start_time = time.time()
    
    pet_msg = pet_pb2.PetMessage()
    pet_msg.ParseFromString(msg_bytes)
    
    if pet_msg.HasField("input_event"):
        print(f"[Python] Received InputEvent: hotkey_id={pet_msg.input_event.hotkey_id}, timestamp={pet_msg.input_event.timestamp}")
    else:
        print(f"[Python] Received unexpected message type: {pet_msg.WhichOneof('message_type')}")

    # 2. Echo an EmotionCommand to Rust
    reply = pet_pb2.PetMessage()
    reply.emotion_command.emotion_id = "happy"
    reply.emotion_command.priority = 10
    
    socket.send(reply.SerializeToString())
    print(f"[Python] Sent EmotionCommand: happy, priority=10")
    
    print(f"[Python] Turnaround time: {(time.time() - start_time) * 1000:.2f} ms")

if __name__ == "__main__":
    main()
