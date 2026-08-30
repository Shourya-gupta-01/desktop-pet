use eframe::egui;
use std::path::Path;
use crossbeam_channel::Receiver;
use std::fs;

use crate::ipc::pet::PetMessage;

/// Holds the raw PNG/JPG bytes of the current sprite.
/// We load the texture lazily on the first frame, then cache the TextureHandle.
pub struct PetWindow {
    sprite_bytes: Option<Vec<u8>>,
    sprite_texture: Option<egui::TextureHandle>,
    ipc_rx: Receiver<PetMessage>,
}

impl PetWindow {
    pub fn new(ipc_rx: Receiver<PetMessage>) -> Self {
        let mut window = Self {
            sprite_bytes: None,
            sprite_texture: None,
            ipc_rx,
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
        // Drain any incoming IPC messages (non-blocking)
        while let Ok(_msg) = self.ipc_rx.try_recv() {
            // In Phase 1 we just log them in the IPC thread, but here we would update state.
            // Example: if msg is EmotionCommand, we might call self.set_sprite(new_path)

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
