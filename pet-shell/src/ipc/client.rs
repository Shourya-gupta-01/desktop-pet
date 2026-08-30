use crossbeam_channel::Sender;
use std::thread;
use std::time::Duration;
use zmq::Context;
use prost::Message;

use super::pet::PetMessage;

pub fn start_ipc_thread(tx: Sender<PetMessage>) {
    thread::spawn(move || {
        let context = Context::new();
        let socket = context.socket(zmq::PAIR).expect("Failed to create ZMQ PAIR socket");
        
        println!("[IPC Client] Connecting to tcp://127.0.0.1:5555...");
        
        // ZMQ will silently handle reconnection if the server is down
        if let Err(e) = socket.connect("tcp://127.0.0.1:5555") {
            println!("[IPC Client] Warning: ZMQ connect returned error: {}", e);
        }

        loop {
            // Block and wait for messages. This is fine because we are on a background thread!
            match socket.recv_bytes(0) {
                Ok(bytes) => {
                    match PetMessage::decode(&bytes[..]) {
                        Ok(msg) => {
                            // Print for debugging checkpoint
                            println!("[IPC Client] Received message: {:?}", msg.message_type);
                            
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
                Err(e) => {
                    println!("[IPC Client] Error receiving bytes: {}", e);
                    // Sleep briefly on error to avoid spinning CPU
                    thread::sleep(Duration::from_millis(500));
                }
            }
        }
    });
}
