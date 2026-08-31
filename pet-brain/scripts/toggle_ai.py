import os
import sys
import zmq

# Add pet-brain root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pet_pb2


def main():
    """Send an instant AI Backend toggle event to the running Desktop Pet Brain."""
    context = zmq.Context()
    socket = context.socket(zmq.PUSH)
    socket.connect("tcp://localhost:5555")

    # Create PetCommand with input_event hotkey_id='toggle_ai'
    cmd = pet_pb2.PetCommand()
    cmd.input_event.hotkey_id = "toggle_ai"
    cmd.input_event.timestamp = 0

    socket.send(cmd.SerializeToString(), zmq.NOBLOCK)
    print("[1-Click Toggle] Sent AI Backend toggle event to Desktop Pet Brain!")


if __name__ == "__main__":
    main()
