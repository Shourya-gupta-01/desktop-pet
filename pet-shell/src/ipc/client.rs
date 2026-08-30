use crossbeam_channel::{Receiver, Sender};
use std::thread;
use std::time::Duration;
use zmq::Context;
use prost::Message;

use super::pet::PetMessage;

pub fn start_ipc_thread(tx: Sender<PetMessage>, rx: Receiver<PetMessage>) {
    thread::spawn(move || {
        let context = Context::new();
        
        // 1. PUSH socket: Sends sensor / input events to Python (Port 5555)
        let push_socket = context.socket(zmq::PUSH).expect("Failed to create ZMQ PUSH socket");
        if let Err(e) = push_socket.connect("tcp://127.0.0.1:5555") {
            println!("[IPC Client] Warning: ZMQ PUSH connect returned error: {}", e);
        }

        // 2. SUB socket: Receives emotion commands and speech bubbles from Python (Port 5554)
        let sub_socket = context.socket(zmq::SUB).expect("Failed to create ZMQ SUB socket");
        if let Err(e) = sub_socket.connect("tcp://127.0.0.1:5554") {
            println!("[IPC Client] Warning: ZMQ SUB connect returned error: {}", e);
        }
        if let Err(e) = sub_socket.set_subscribe(b"") {
            println!("[IPC Client] Failed to subscribe to all topics: {}", e);
        }
        
        println!("[IPC Client] Connected to Python Brain (PUSH: 5555, SUB: 5554)!");

        loop {
            // 1. Check for outgoing messages from the UI / sensor threads
            while let Ok(msg) = rx.try_recv() {
                let mut buf = Vec::new();
                if msg.encode(&mut buf).is_ok() {
                    if let Err(e) = push_socket.send(&buf, 0) {
                        println!("[IPC Client] Failed to push message over ZMQ: {}", e);
                    }
                }
            }

            // 2. Check for incoming messages from Python (non-blocking)
            match sub_socket.recv_bytes(zmq::DONTWAIT) {
                Ok(bytes) => {
                    match PetMessage::decode(&bytes[..]) {
                        Ok(msg) => {
                            // Forward the parsed message to the main UI thread
                            if let Err(e) = tx.send(msg) {
                                println!("[IPC Client] Error forwarding message to UI: {}", e);
                            }
                        },
                        Err(e) => {
                            println!("[IPC Client] Failed to decode protobuf: {}", e);
                        }
                    }
                },
                Err(zmq::Error::EAGAIN) => {
                    // Normal behavior when no message is waiting
                },
                Err(e) => {
                    println!("[IPC Client] Error receiving bytes: {}", e);
                }
            }

            // Sleep briefly to prevent 100% CPU usage
            thread::sleep(Duration::from_millis(10));
        }
    });
}
