use eframe::egui;

fn main() -> eframe::Result<()> {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_decorations(false)
            .with_transparent(true)
            .with_always_on_top()
            .with_inner_size([400.0, 300.0])
            .with_mouse_passthrough(true),
        ..Default::default()
    };

    eframe::run_native(
        "Chibi Pet Window Test",
        options,
        Box::new(|_cc| Ok(Box::<MyApp>::default())),
    )
}

#[derive(Default)]
struct MyApp {}

impl eframe::App for MyApp {
    fn clear_color(&self, _visuals: &egui::Visuals) -> [f32; 4] {
        egui::Color32::TRANSPARENT.to_normalized_gamma_f32()
    }

    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        egui::CentralPanel::default()
            .frame(egui::Frame::default().fill(egui::Color32::TRANSPARENT))
            .show(ctx, |ui| {
                ui.centered_and_justified(|ui| {
                    ui.heading(
                        egui::RichText::new("Hello from Pet!")
                            .color(egui::Color32::WHITE)
                            .background_color(egui::Color32::from_black_alpha(150))
                            .size(30.0),
                    );
                });
            });
    }
}
