//! SVG to BMP Converter for SpoolBuddy
//!
//! Converts SVG assets to BMP format suitable for embedded-graphics.
//! Outputs 16-bit RGB565 BMPs for ESP32 display.

use image::{ImageBuffer, Rgb, RgbImage};
use resvg::tiny_skia::Pixmap;
use resvg::usvg::{Options, Tree};
use std::fs;
use std::path::Path;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let svg_dir = Path::new("assets/svg");
    let bmp_dir = Path::new("assets/bmp");

    fs::create_dir_all(bmp_dir)?;

    println!("SVG to BMP Converter for SpoolBuddy");
    println!("====================================\n");

    // Define icons to convert with their target sizes
    let icons = [
        ("ams_icon.svg", 64),
        ("ams_4_tray.svg", 80),
        ("filament.svg", 48),
        ("ams_rfid_0.svg", 32),
        ("ams_humidity_4.svg", 32),
        ("check_on.svg", 24),
        ("info.svg", 24),
    ];

    for (svg_name, size) in &icons {
        let svg_path = svg_dir.join(svg_name);
        if !svg_path.exists() {
            println!("Skipping {} (not found)", svg_name);
            continue;
        }

        let bmp_name = svg_name.replace(".svg", ".bmp");
        let bmp_path = bmp_dir.join(&bmp_name);

        println!("Converting {} -> {} ({}x{})", svg_name, bmp_name, size, size);

        match convert_svg(&svg_path, &bmp_path, *size) {
            Ok(_) => println!("  OK"),
            Err(e) => println!("  ERROR: {}", e),
        }
    }

    println!("\nDone! BMPs saved to assets/bmp/");
    Ok(())
}

fn convert_svg(
    svg_path: &Path,
    bmp_path: &Path,
    size: u32,
) -> Result<(), Box<dyn std::error::Error>> {
    // Read and parse SVG
    let svg_data = fs::read(svg_path)?;
    let opt = Options::default();
    let tree = Tree::from_data(&svg_data, &opt)?;

    // Calculate scale to fit in target size
    let svg_size = tree.size();
    let scale = (size as f32 / svg_size.width()).min(size as f32 / svg_size.height());

    let width = (svg_size.width() * scale).ceil() as u32;
    let height = (svg_size.height() * scale).ceil() as u32;

    // Render to pixmap
    let mut pixmap = Pixmap::new(width, height).ok_or("Failed to create pixmap")?;

    // Fill with transparent background
    pixmap.fill(tiny_skia::Color::TRANSPARENT);

    let transform = tiny_skia::Transform::from_scale(scale, scale);
    resvg::render(&tree, transform, &mut pixmap.as_mut());

    // Convert to RGB image
    let mut img: RgbImage = ImageBuffer::new(width, height);

    for y in 0..height {
        for x in 0..width {
            let pixel = pixmap.pixel(x, y).unwrap();
            // Pre-multiplied alpha to straight alpha
            let a = pixel.alpha() as f32 / 255.0;
            let (r, g, b) = if a > 0.0 {
                (
                    (pixel.red() as f32 / a).min(255.0) as u8,
                    (pixel.green() as f32 / a).min(255.0) as u8,
                    (pixel.blue() as f32 / a).min(255.0) as u8,
                )
            } else {
                (0, 0, 0) // Transparent -> black (will be background)
            };

            // Blend with dark background for transparent areas
            let bg = 0x1f; // Dark gray background
            let r_out = ((r as u16 * pixel.alpha() as u16 + bg as u16 * (255 - pixel.alpha() as u16)) / 255) as u8;
            let g_out = ((g as u16 * pixel.alpha() as u16 + bg as u16 * (255 - pixel.alpha() as u16)) / 255) as u8;
            let b_out = ((b as u16 * pixel.alpha() as u16 + bg as u16 * (255 - pixel.alpha() as u16)) / 255) as u8;

            img.put_pixel(x, y, Rgb([r_out, g_out, b_out]));
        }
    }

    // Save as BMP
    img.save(bmp_path)?;

    Ok(())
}
