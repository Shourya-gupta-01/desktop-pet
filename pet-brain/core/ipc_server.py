import zmq
import sys
import os

# Add the parent directory to sys.path so we can import pet_pb2
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pet_pb2

class IPCServer:
    def __init__(self, in_address="tcp://127.0.0.1:5555", out_address="tcp://127.0.0.1:5554"):
        self.context = zmq.Context()
        self.in_socket = self.context.socket(zmq.PULL)
        self.out_socket = self.context.socket(zmq.PUB)
        self.in_address = in_address
        self.out_address = out_address
        
    def start(self):
        print(f"[IPC Server] Binding PULL to {self.in_address} (Sensors from Rust)...")
        self.in_socket.bind(self.in_address)
        print(f"[IPC Server] Binding PUB to {self.out_address} (Commands to Rust UI)...")
        self.out_socket.bind(self.out_address)
        print("[IPC Server] Ready and waiting for connections.")
        
    def send_message(self, message: pet_pb2.PetMessage):
        """Serialize and publish a protobuf message over ZMQ."""
        try:
            serialized_bytes = message.SerializeToString()
            self.out_socket.send(serialized_bytes)
        except Exception as e:
            print(f"[IPC Server] Error publishing message: {e}")
        
    def receive_message(self, blocking=False) -> pet_pb2.PetMessage | None:
        """Attempt to receive and deserialize a protobuf message from Rust."""
        flags = 0 if blocking else zmq.NOBLOCK
        try:
            message_bytes = self.in_socket.recv(flags)
            msg = pet_pb2.PetMessage()
            msg.ParseFromString(message_bytes)
            return msg
        except zmq.Again:
            return None
        except Exception as e:
            print(f"[IPC Server] Error receiving message: {e}")
            return None
