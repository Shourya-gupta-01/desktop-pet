use prost::Message;
use std::time::{SystemTime, UNIX_EPOCH, Instant};
use zmq::Context;

// Include the generated protobuf code
pub mod pet {
    include!(concat!(env!("OUT_DIR"), "/pet.rs"));
}

fn main() {
    let context = Context::new();
    let socket = context.socket(zmq::PAIR).unwrap();
    println!("[Rust] Connecting to tcp://127.0.0.1:5555...");
    socket.connect("tcp://127.0.0.1:5555").unwrap();

    let start_time = Instant::now();

    // 1. Create and send InputEvent
    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_millis() as u64;

    let input_event = pet::InputEvent {
        hotkey_id: "ctrl+shift+a".to_string(),
        timestamp,
    };

    let msg = pet::PetMessage {
        message_type: Some(pet::pet_message::MessageType::InputEvent(input_event)),
    };

    let mut buf = Vec::new();
    msg.encode(&mut buf).unwrap();

    println!("[Rust] Sending InputEvent...");
    socket.send(&buf, 0).unwrap();

    // 2. Receive EmotionCommand
    let reply_bytes = socket.recv_bytes(0).unwrap();
    let reply = pet::PetMessage::decode(&reply_bytes[..]).unwrap();

    if let Some(pet::pet_message::MessageType::EmotionCommand(emotion_cmd)) = reply.message_type {
        println!("[Rust] Received EmotionCommand: {}, priority={}", emotion_cmd.emotion_id, emotion_cmd.priority);
    } else {
        println!("[Rust] Received unexpected message!");
    }

    let elapsed = start_time.elapsed();
    println!("[Rust] Turnaround time (including Rust encode/decode): {:.2?} ms", elapsed.as_secs_f64() * 1000.0);
}
