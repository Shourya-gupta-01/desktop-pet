use eframe::egui;
use std::path::Path;
use crossbeam_channel::{Receiver, Sender};
use std::fs;

use crate::ipc::pet::{PetMessage, pet_message::MessageType};

/// Holds the raw PNG/JPG bytes of the current sprite.
/// We load the texture lazily on the first frame, then cache the TextureHandle.
pub struct PetWindow {
    sprite_bytes: Option<Vec<u8>>,
    sprite_texture: Option<egui::TextureHandle>,
    ipc_rx: Receiver<PetMessage>,
    _ipc_tx: Sender<PetMessage>,
    speech_text: Option<String>,
    speech_expiry: Option<std::time::Instant>,
    debug_printed: bool,
}

impl PetWindow {
    pub fn new(ipc_rx: Receiver<PetMessage>, ipc_tx: Sender<PetMessage>) -> Self {
        let mut window = Self {
            sprite_bytes: None,
            sprite_texture: None,
            ipc_rx,
            _ipc_tx: ipc_tx,
            speech_text: None,
            speech_expiry: None,
            debug_printed: false,
        };

        // Load the initial static placeholder sprite
        let initial_sprite = Self::resolve_sprite("idle").unwrap_or_else(|| "../assets/sprites/idle/placeholder.png".to_string());
        window.set_sprite(&initial_sprite);
        window
    }

    /// Resolve an emotion identifier to an existing sprite image path across install & dev roots.
    pub fn resolve_sprite(emotion: &str) -> Option<String> {
        let emotion_clean = emotion.trim().to_lowercase();
        let mut candidates = vec![emotion_clean.clone()];
        if emotion_clean == "bored" {
            candidates.push("boredom".to_string());
        } else if emotion_clean == "boredom" {
            candidates.push("bored".to_string());
        }

        let file_names = ["placeholder.png", "pasted file.png", "sprite.png", "placeholder.jpg", "sprite.jpg"];

        // Collect potential asset root directories
        let mut asset_roots = Vec::new();

        if let Ok(env_assets) = std::env::var("DESKTOP_PET_ASSETS_DIR") {
            asset_roots.push(std::path::PathBuf::from(env_assets));
        }

        if let Ok(exe_path) = std::env::current_exe() {
            if let Some(exe_dir) = exe_path.parent() {
                asset_roots.push(exe_dir.join("../assets/sprites"));
                asset_roots.push(exe_dir.join("assets/sprites"));
            }
        }

        if let Ok(home) = std::env::var("HOME") {
            asset_roots.push(std::path::PathBuf::from(home).join(".local/share/desktop-pet/assets/sprites"));
        }

        asset_roots.push(std::path::PathBuf::from("assets/sprites"));
        asset_roots.push(std::path::PathBuf::from("../assets/sprites"));

        for root in &asset_roots {
            for emo in &candidates {
                for fname in &file_names {
                    let p = root.join(emo).join(fname);
                    if p.exists() {
                        return Some(p.to_string_lossy().to_string());
                    }
                }
            }
        }

        // Fallback to idle in any asset root
        for root in &asset_roots {
            for fname in &file_names {
                let p = root.join("idle").join(fname);
                if p.exists() {
                    return Some(p.to_string_lossy().to_string());
                }
            }
        }

        None
    }

    /// Read a sprite image from disk and store the raw bytes.
    /// The texture will be created on the next frame (we need an egui Context for that).
    pub fn set_sprite(&mut self, path: &str) {
        let resolved = if Path::new(path).exists() {
            Some(path.to_string())
        } else {
            Self::resolve_sprite(path)
        };

        if let Some(valid_path) = resolved {
            match fs::read(&valid_path) {
                Ok(data) => {
                    self.sprite_bytes = Some(data);
                    // Invalidate the old cached texture so it gets re-created next frame
                    self.sprite_texture = None;
                    println!("[Window] Loaded sprite from: {}", valid_path);
                }
                Err(e) => {
                    println!("[Window] Error reading sprite file {}: {}", valid_path, e);
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
        // Since mouse passthrough is active, the window never receives OS input focus.
        // We request a continuous 30fps repaint so incoming IPC messages are drained immediately.
        ctx.request_repaint_after(std::time::Duration::from_millis(33));

        // Drain any incoming IPC messages (non-blocking)
        while let Ok(msg) = self.ipc_rx.try_recv() {
            match msg.message_type {
                Some(MessageType::EmotionCommand(cmd)) => {
                    println!("[Window] Received EmotionCommand: {}", cmd.emotion_id);
                    self.set_sprite(&cmd.emotion_id);
                }
                Some(MessageType::SpeechBubble(bubble)) => {
                    println!("[Window] Received SpeechBubble: {}", bubble.text);
                    let full_len = if bubble.is_streaming_chunk {
                        let text = self.speech_text.get_or_insert_with(String::new);
                        text.push_str(&bubble.text);
                        text.len()
                    } else {
                        let len = bubble.text.len();
                        self.speech_text = Some(bubble.text);
                        len
                    };
                    // Generous reading duration: at least 10s, scaling up with text length
                    let reading_secs = 10.0 + (full_len as f32 / 12.0);
                    self.speech_expiry = Some(std::time::Instant::now() + std::time::Duration::from_secs_f32(reading_secs.min(25.0)));
                }
                _ => {}
            }
            ctx.request_repaint();
        }

        // Check for speech bubble expiry
        if let Some(expiry) = self.speech_expiry {
            if std::time::Instant::now() >= expiry {
                self.speech_text = None;
                self.speech_expiry = None;
                ctx.request_repaint();
            }
        }

        // Ensure the sprite texture is loaded (lazy init)
        self.ensure_texture(ctx);

        // Render the transparent background, speech bubble, and sprite
        egui::CentralPanel::default()
            .frame(egui::Frame::default().fill(egui::Color32::TRANSPARENT))
            .show(ctx, |ui| {
                let rect = ui.max_rect();
                let w = rect.width();
                let h = rect.height();

                if !self.debug_printed {
                    println!("[Window] DEBUG: Actual window rect = {:.0}x{:.0} (min={:.0},{:.0} max={:.0},{:.0})", w, h, rect.min.x, rect.min.y, rect.max.x, rect.max.y);
                    self.debug_printed = true;
                }

                // Pet sprite is 200x200. Anchor it to bottom-right corner.
                let pet_w = 200.0_f32;
                let pet_pad = 15.0_f32; // padding from edges
                let pet_x = rect.max.x - pet_w - pet_pad;
                let pet_y = rect.max.y - pet_w - pet_pad;

                // 1. Render Pet Sprite at fixed bottom-right (NEVER moves)
                if let Some(texture) = &self.sprite_texture {
                    let sprite_rect = egui::Rect::from_min_size(
                        egui::pos2(pet_x, pet_y),
                        egui::vec2(pet_w, pet_w),
                    );
                    ui.put(
                        sprite_rect,
                        egui::Image::new(texture)
                            .tint(egui::Color32::from_rgba_unmultiplied(255, 255, 255, 190)),
                    );
                }

                // 2. Speech Bubble: positioned RIGHT NEXT to the pet (not far away)
                //    Translucent frosted glass styling so background content is visible
                if let Some(speech) = &self.speech_text {
                    let bubble_width = 380.0_f32;          // Fixed readable width
                    let bubble_right = pet_x - 15.0;       // 15px gap between bubble and pet
                    let bubble_left = bubble_right - bubble_width;
                    let bubble_top = pet_y + 20.0;         // Vertically aligned with pet
                    let bubble_bottom = rect.max.y - pet_pad - 20.0;

                    let bubble_area = egui::Rect::from_min_max(
                        egui::pos2(bubble_left, bubble_top),
                        egui::pos2(bubble_right, bubble_bottom),
                    );

                    ui.allocate_ui_at_rect(bubble_area, |ui| {
                        ui.with_layout(egui::Layout::centered_and_justified(egui::Direction::TopDown), |ui| {
                            egui::Frame::none()
                                .fill(egui::Color32::from_rgba_unmultiplied(14, 16, 26, 130))
                                .stroke(egui::Stroke::new(1.0_f32, egui::Color32::from_rgba_unmultiplied(255, 255, 255, 110)))
                                .rounding(14.0)
                                .inner_margin(egui::Margin::symmetric(16.0, 12.0))
                                .show(ui, |ui| {
                                    ui.set_max_width(bubble_width - 32.0);
                                    ui.add(
                                        egui::Label::new(
                                            egui::RichText::new(speech)
                                                .color(egui::Color32::WHITE)
                                                .size(14.0)
                                                .line_height(Some(20.0))
                                                .strong(),
                                        )
                                        .wrap(),
                                    );
                                });
                        });
                    });
                }
            });
    }
}
