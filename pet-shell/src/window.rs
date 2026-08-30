use eframe::egui;
use std::path::Path;
use crossbeam_channel::{Receiver, Sender};
use std::fs;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::ipc::pet::{PetMessage, InputEvent, pet_message::MessageType};

/// Holds the raw PNG/JPG bytes of the current sprite.
/// We load the texture lazily on the first frame, then cache the TextureHandle.
pub struct PetWindow {
    sprite_bytes: Option<Vec<u8>>,
    sprite_texture: Option<egui::TextureHandle>,
    ipc_rx: Receiver<PetMessage>,
    ipc_tx: Sender<PetMessage>,
}

impl PetWindow {
    pub fn new(ipc_rx: Receiver<PetMessage>, ipc_tx: Sender<PetMessage>) -> Self {
        let mut window = Self {
            sprite_bytes: None,
            sprite_texture: None,
            ipc_rx,
            ipc_tx,
        };

        // Load the initial static placeholder sprite
        window.set_sprite("../assets/sprites/idle/placeholder.png");
        window
    }

    /// Read a sprite image from disk and store the raw bytes.
    /// The texture will be created on the next frame (we need an egui Context for that).
    pub fn set_sprite(&mut self, path: &str) {
        if Path::new(path).exists() {
            match fs::read(path) {
                Ok(data) => {
                    self.sprite_bytes = Some(data);
                    // Invalidate the old cached texture so it gets re-created next frame
                    self.sprite_texture = None;
                    println!("[Window] Loaded sprite from: {}", path);
                }
                Err(e) => {
                    println!("[Window] Error reading sprite file {}: {}", path, e);
                }
            }
        } else {
            println!("[Window] Warning: Sprite path not found: {}", path);
        }
    }

    /// Lazily decode the sprite bytes into an egui TextureHandle.
    /// Must be called inside `update()` where we have access to the Context.
    fn ensure_texture(&mut self, ctx: &egui::Context) {
        if self.sprite_texture.is_some() {
            return; // Already loaded
        }

        if let Some(bytes) = &self.sprite_bytes {
            // Use the `image` crate (already a dependency) to decode PNG/JPG bytes
            match image::load_from_memory(bytes) {
                Ok(img) => {
                    let rgba = img.to_rgba8();
                    let size = [rgba.width() as usize, rgba.height() as usize];
                    let pixels = rgba.as_flat_samples();

                    let color_image = egui::ColorImage::from_rgba_unmultiplied(
                        size,
                        pixels.as_slice(),
                    );

                    let texture = ctx.load_texture(
                        "pet_sprite",
                        color_image,
                        egui::TextureOptions::LINEAR,
                    );

                    self.sprite_texture = Some(texture);
                }
                Err(e) => {
                    println!("[Window] Error decoding sprite image: {}", e);
                    // Clear the bytes so we don't retry every frame
                    self.sprite_bytes = None;
                }
            }
        }
    }
}

impl eframe::App for PetWindow {
    fn clear_color(&self, _visuals: &egui::Visuals) -> [f32; 4] {
        egui::Color32::TRANSPARENT.to_normalized_gamma_f32()
    }

    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        // --- PHASE 2 CHECKPOINT: SEND INPUT EVENT ---
        // If the user presses Space while the window is focused, send an event to Python.
        ctx.input(|i| {
            if i.key_pressed(egui::Key::Space) {
                let timestamp = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_millis() as u64;
                let event = InputEvent {
                    hotkey_id: "space_test".to_string(),
                    timestamp,
                };
                let msg = PetMessage {
                    message_type: Some(MessageType::InputEvent(event)),
                };
                if let Err(e) = self.ipc_tx.send(msg) {
                    println!("[Window] Failed to send InputEvent: {}", e);
                } else {
                    println!("[Window] Sent InputEvent to Brain!");
                }
            }
        });

        // Drain any incoming IPC messages (non-blocking)
        while let Ok(msg) = self.ipc_rx.try_recv() {
            if let Some(MessageType::EmotionCommand(cmd)) = msg.message_type {
                println!("[Window] Received EmotionCommand: {}", cmd.emotion_id);
                // Dynamically change sprite based on emotion!
                let path = format!("../assets/sprites/{}/placeholder.png", cmd.emotion_id);
                self.set_sprite(&path);
            }
            // Request a repaint so the window updates if state changed
            ctx.request_repaint();
        }

        // Ensure the sprite texture is loaded (lazy init)
        self.ensure_texture(ctx);

        // Render the transparent background and our sprite
        egui::CentralPanel::default()
            .frame(egui::Frame::default().fill(egui::Color32::TRANSPARENT))
            .show(ctx, |ui| {
                ui.centered_and_justified(|ui| {
                    if let Some(texture) = &self.sprite_texture {
                        let size = texture.size_vec2();
                        ui.image(egui::load::SizedTexture::new(texture.id(), size));
                    } else {
                        // Fallback text if no sprite loaded
                        ui.heading(
                            egui::RichText::new("No Sprite Loaded")
                                .color(egui::Color32::RED),
                        );
                    }
                });
            });
    }
}
