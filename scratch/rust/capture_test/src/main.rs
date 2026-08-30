use xcap::Monitor;

fn main() {
    let monitors = Monitor::all().unwrap();
    
    if let Some(monitor) = monitors.first() {
        // monitor.name() returns a Result<String, XCapError> so we unwrap it
        println!("Capturing screen from monitor: {}", monitor.name().unwrap());
        let image = monitor.capture_image().unwrap();
        
        let path = "screenshot.png";
        image.save(path).unwrap();
        println!("Successfully saved screen capture to {}", path);
    } else {
        println!("No monitors found!");
    }
}
