use crossbeam_channel::{Receiver, Sender};
use std::thread;
use std::time::Duration;
use zmq::Context;
use prost::Message;

use super::pet::PetMessage;

pub fn start_ipc_thread(tx: Sender<PetMessage>, rx: Receiver<PetMessage>) {
    thread::spawn(move || {
        let context = Context::new();
        let socket = context.socket(zmq::PAIR).expect("Failed to create ZMQ PAIR socket");
        
        println!("[IPC Client] Connecting to tcp://127.0.0.1:5555...");
        
        // ZMQ will silently handle reconnection if the server is down
        if let Err(e) = socket.connect("tcp://127.0.0.1:5555") {
            println!("[IPC Client] Warning: ZMQ connect returned error: {}", e);
        }

        loop {
            // 1. Check for outgoing messages from the UI thread
            while let Ok(msg) = rx.try_recv() {
                let mut buf = Vec::new();
                if msg.encode(&mut buf).is_ok() {
                    if let Err(e) = socket.send(&buf, 0) {
                        println!("[IPC Client] Failed to send message over ZMQ: {}", e);
                    }
                }
            }

            // 2. Check for incoming messages from Python (non-blocking)
            match socket.recv_bytes(zmq::DONTWAIT) {
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
