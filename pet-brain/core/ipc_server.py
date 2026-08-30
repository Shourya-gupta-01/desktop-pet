import zmq
import sys
import os

# Add the parent directory to sys.path so we can import pet_pb2
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pet_pb2

class IPCServer:
    def __init__(self, address="tcp://127.0.0.1:5555"):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PAIR)
        self.address = address
        
    def start(self):
        print(f"[IPC Server] Binding to {self.address}...")
        self.socket.bind(self.address)
        print("[IPC Server] Ready and waiting for connections.")
        
    def send_message(self, message: pet_pb2.PetMessage):
        """Serialize and send a protobuf message over ZMQ."""
        serialized_bytes = message.SerializeToString()
        self.socket.send(serialized_bytes)
        
    def receive_message(self, blocking=False) -> pet_pb2.PetMessage | None:
        """Attempt to receive and deserialize a protobuf message."""
        flags = 0 if blocking else zmq.NOBLOCK
        try:
            message_bytes = self.socket.recv(flags)
            msg = pet_pb2.PetMessage()
            msg.ParseFromString(message_bytes)
            return msg
        except zmq.Again:
            # Raised when non-blocking and no message is available
            return None
        except Exception as e:
            print(f"[IPC Server] Error receiving message: {e}")
            return None
