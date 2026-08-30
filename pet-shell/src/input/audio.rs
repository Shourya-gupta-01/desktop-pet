use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use crossbeam_channel::Sender;
use std::thread;
use std::time::{Duration, Instant};

use crate::ipc::pet::{pet_message::MessageType, AudioEvent, PetMessage};

pub fn start_audio_listener(tx: Sender<PetMessage>) {
    thread::spawn(move || {
        println!("[Audio] Starting ambient audio listener...");

        let host = cpal::default_host();
        let device = match host.default_input_device() {
            Some(d) => d,
            None => {
                println!("[Audio] No default input device found.");
                return;
            }
        };

        println!("[Audio] Using input device: {}", device.name().unwrap_or_else(|_| "Unknown".to_string()));

        let config = match device.default_input_config() {
            Ok(c) => c,
            Err(e) => {
                println!("[Audio] Failed to get default input config: {}", e);
                return;
            }
        };

        let err_fn = move |err| {
            println!("[Audio] An error occurred on the input audio stream: {}", err);
        };

        // We use a shared boolean/timestamp to throttle events so we don't spam IPC
        // but since we are inside a stream closure which runs on cpal's real-time thread,
        // we can just send directly to the channel. The channel is non-blocking.
        let tx_clone = tx.clone();
        
        // This is a bit tricky: the stream callback is called frequently.
        // We'll track the last time we sent an event to avoid flooding.
        // `Cell` or `Mutex` would be needed if shared, but since it's just the callback thread,
        // we can use a small struct or just a static-like pattern. But since it's a `move` closure,
        // we can capture a mutable variable. Wait, `build_input_stream` requires `Send` closure,
        // and might be called concurrently? No, usually sequentially per chunk.
        
        let stream = match config.sample_format() {
            cpal::SampleFormat::F32 => {
                let mut last_event_time = Instant::now();
                let mut candidate: Option<(f32, Instant)> = None;

                device.build_input_stream(
                    &config.into(),
                    move |data: &[f32], _: &cpal::InputCallbackInfo| {
                        let mut sum_squares = 0.0;
                        let mut peak = 0.0_f32;
                        for &sample in data {
                            let abs_sample = sample.abs();
                            if abs_sample > peak {
                                peak = abs_sample;
                            }
                            sum_squares += sample * sample;
                        }
                        let rms = (sum_squares / data.len() as f32).sqrt();

                        // 1. Verify previous impulse candidate:
                        // A true clap dies down within < 40ms. If sound is sustained, it is speech/yelling.
                        if let Some((candidate_peak, candidate_time)) = candidate {
                            let elapsed = candidate_time.elapsed();
                            if elapsed < Duration::from_millis(60) {
                                if rms > 0.08 {
                                    // Sound is sustained across consecutive chunks -> It's speech/voice, cancel!
                                    candidate = None;
                                } else if elapsed >= Duration::from_millis(8) {
                                    // Sound sharply dropped to silence -> Confirmed acoustic clap impulse!
                                    candidate = None;
                                    if last_event_time.elapsed() > Duration::from_millis(600) {
                                        println!(
                                            "[Audio] Confirmed Clap! Peak: {:.2}, Immediate Decay: RMS {:.3}",
                                            candidate_peak, rms
                                        );
                                        last_event_time = Instant::now();

                                        let msg = PetMessage {
                                            message_type: Some(MessageType::AudioEvent(AudioEvent {
                                                amplitude: candidate_peak,
                                                is_clap: true,
                                            })),
                                        };
                                        let _ = tx_clone.send(msg);
                                    }
                                }
                            } else {
                                candidate = None;
                            }
                        }

                        // 2. Detect initial sharp percussive impulse (Peak >= 0.45, Crest Factor >= 3.8)
                        if candidate.is_none() && rms > 0.01 && peak >= 0.45 {
                            let crest_factor = peak / rms;
                            if crest_factor >= 3.8 && last_event_time.elapsed() > Duration::from_millis(600) {
                                candidate = Some((peak, Instant::now()));
                            }
                        }
                    },
                    err_fn,
                    None,
                )
            },
            // We can implement other formats later if needed, F32 is most common for modern audio
            _ => {
                println!("[Audio] Unsupported sample format.");
                return;
            }
        };

        let stream = match stream {
            Ok(s) => s,
            Err(e) => {
                println!("[Audio] Failed to build audio stream: {}", e);
                return;
            }
        };

        if let Err(e) = stream.play() {
            println!("[Audio] Failed to start audio stream: {}", e);
            return;
        }

        // Keep the thread alive so the stream doesn't drop
        loop {
            thread::sleep(Duration::from_secs(1));
        }
    });
}
