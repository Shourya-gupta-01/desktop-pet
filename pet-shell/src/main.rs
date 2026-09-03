mod ipc;
mod window;
mod input;
mod sidecar;

use crossbeam_channel::unbounded;
use eframe::egui;
use window::PetWindow;
use sidecar::SidecarSupervisor;

fn main() -> eframe::Result<()> {
    // 1. Start the Sidecar Supervisor (automatically spawns & monitors pet-brain)
    let _supervisor = SidecarSupervisor::start();

    // 2. Set up the IPC communication channel
    let (ipc_tx, ipc_rx) = unbounded(); // IPC thread -> UI thread
    let (ui_tx, ui_rx) = unbounded();   // UI thread -> IPC thread

    // 3. Start the background sensor threads (Input & Audio)
    input::hotkeys::start_hotkey_listener(ui_tx.clone());
    input::audio::start_audio_listener(ui_tx.clone());

    // 4. Start the ZeroMQ background thread
    // This allows the Rust UI to start instantly and reconnect even if Python is loading
    ipc::client::start_ipc_thread(ipc_tx, ui_rx);

    // 5. Configure the transparent UI Window
    //    .with_app_id() sets the Wayland app_id so Hyprland can match windowrules against it.
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_decorations(false)
            .with_transparent(true)
            .with_always_on_top()
            .with_inner_size([620.0, 230.0])            // Matches Hyprland rule: 620x230 for side-by-side layout
            .with_position(egui::pos2(1300.0, 850.0))   // Hyprland overrides this via windowrule
            .with_mouse_passthrough(true)
            .with_app_id("desktop-pet".to_string()),     // Wayland app_id for Hyprland rules
        ..Default::default()
    };

    println!("[Main] Starting pet-shell UI...");

    // 6. Run the app
    eframe::run_native(
        "Desktop Pet Shell",
        options,
        Box::new(|_cc| Ok(Box::new(PetWindow::new(ipc_rx, ui_tx)))),
    )
}
