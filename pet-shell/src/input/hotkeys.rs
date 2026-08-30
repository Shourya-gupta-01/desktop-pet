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
            if let Ok((amt, _src)) = socket.recv_from(&mut buf) {
                let payload = String::from_utf8_lossy(&buf[..amt]).trim().to_string();
                let hotkey_id = if payload.is_empty() || payload == "trigger" {
                    "global_action_x".to_string()
                } else {
                    payload
                };

                println!("[Hotkeys] Received trigger via UDP: '{}'", hotkey_id);

                let timestamp = SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap()
                    .as_millis() as u64;

                let msg = PetMessage {
                    message_type: Some(MessageType::InputEvent(InputEvent {
                        hotkey_id,
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
