use crossbeam_channel::Sender;
use std::net::UdpSocket;
use std::thread;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::ipc::pet::{pet_message::MessageType, InputEvent, PetMessage};

pub fn start_hotkey_listener(tx: Sender<PetMessage>) {
    thread::spawn(move || {
        println!("[Hotkeys] Starting local UDP listener for Wayland hotkeys on port 5556...");

        let socket = match UdpSocket::bind("127.0.0.1:5556") {
            Ok(s) => s,
            Err(e) => {
                println!("[Hotkeys] Failed to bind UDP socket: {}", e);
                return;
            }
        };

        let mut buf = [0; 64];

        loop {
            if let Ok(_) = socket.recv_from(&mut buf) {
                println!("[Hotkeys] Received trigger via UDP!");

                let timestamp = SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap()
                    .as_millis() as u64;

                let msg = PetMessage {
                    message_type: Some(MessageType::InputEvent(InputEvent {
                        hotkey_id: "global_action_x".to_string(),
                        timestamp,
                    })),
                };

                if let Err(e) = tx.send(msg) {
                    println!("[Hotkeys] Failed to send to IPC thread: {}", e);
                }
            }
        }
    });
}
