mod ipc;
mod window;
mod input;

use crossbeam_channel::unbounded;
use eframe::egui;
use window::PetWindow;

fn main() -> eframe::Result<()> {
    // 1. Set up the IPC communication channel
    let (ipc_tx, ipc_rx) = unbounded(); // IPC thread -> UI thread
    let (ui_tx, ui_rx) = unbounded();   // UI thread -> IPC thread

    // 2. Start the background sensor threads (Input & Audio)
    input::hotkeys::start_hotkey_listener(ui_tx.clone());
    input::audio::start_audio_listener(ui_tx.clone());

    // 3. Start the ZeroMQ background thread
    // This allows the Rust UI to start instantly even if Python is dead/loading
    ipc::client::start_ipc_thread(ipc_tx, ui_rx);

    // 3. Configure the transparent UI Window
    //    .with_app_id() sets the Wayland app_id so Hyprland can match windowrules against it.
    //    Without this, the class is empty and Hyprland treats it as a regular tiled window.
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_decorations(false)
            .with_transparent(true)
            .with_always_on_top()
            .with_inner_size([200.0, 200.0])            // Compact size for the chibi sprite
            .with_position(egui::pos2(1700.0, 850.0))   // Bottom-right corner (adjust to your resolution)
            .with_mouse_passthrough(true)
            .with_app_id("desktop-pet".to_string()),     // Wayland app_id for Hyprland rules
        ..Default::default()
    };

    println!("[Main] Starting pet-shell UI...");

    // 4. Run the app
    eframe::run_native(
        "Desktop Pet Shell",
        options,
        Box::new(|_cc| Ok(Box::new(PetWindow::new(ipc_rx, ui_tx)))),
    )
}
