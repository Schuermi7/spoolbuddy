//! SpoolBuddy GUI Screenshot Generator
//!
//! Generates PNG screenshots of all GUI screens for preview.
//!
//! Run with: cargo run --target x86_64-unknown-linux-gnu
//!
//! Outputs: screenshots/*.png

use embedded_graphics::{
    mono_font::{ascii::FONT_10X20, ascii::FONT_6X10, MonoTextStyle},
    pixelcolor::Rgb565,
    prelude::*,
    primitives::{Circle, Line, PrimitiveStyle, Rectangle, RoundedRectangle},
    text::{Alignment, Text},
};
use image::{DynamicImage, GenericImageView, ImageBuffer, Rgb};
use std::path::Path;

// Embedded icon data (loaded at startup)
struct IconSet {
    ams_icon: Option<IconData>,
    filament: Option<IconData>,
}

struct IconData {
    width: u32,
    height: u32,
    pixels: Vec<Rgb565>,
}

impl IconData {
    fn load(path: &Path) -> Option<Self> {
        let img = image::open(path).ok()?;
        let (width, height) = img.dimensions();
        let mut pixels = Vec::with_capacity((width * height) as usize);

        for y in 0..height {
            for x in 0..width {
                let pixel = img.get_pixel(x, y);
                // Convert RGB888 to RGB565
                let r = (pixel[0] >> 3) as u16;
                let g = (pixel[1] >> 2) as u16;
                let b = (pixel[2] >> 3) as u16;
                let rgb565 = (r << 11) | (g << 5) | b;
                pixels.push(Rgb565::new(
                    (pixel[0] >> 3) as u8,
                    (pixel[1] >> 2) as u8,
                    (pixel[2] >> 3) as u8,
                ));
            }
        }

        Some(IconData { width, height, pixels })
    }

    fn draw(&self, fb: &mut Framebuffer, x: i32, y: i32) {
        for py in 0..self.height as i32 {
            for px in 0..self.width as i32 {
                let idx = (py as u32 * self.width + px as u32) as usize;
                if idx < self.pixels.len() {
                    let color = self.pixels[idx];
                    // Skip near-black pixels (transparent background)
                    if color.r() > 2 || color.g() > 4 || color.b() > 2 {
                        let _ = Pixel(Point::new(x + px, y + py), color).draw(fb);
                    }
                }
            }
        }
    }
}

fn load_icons() -> IconSet {
    let bmp_dir = Path::new("assets/bmp");
    IconSet {
        ams_icon: IconData::load(&bmp_dir.join("ams_icon.bmp")),
        filament: IconData::load(&bmp_dir.join("filament.bmp")),
    }
}

// Display dimensions
const DISPLAY_WIDTH: u32 = 800;
const DISPLAY_HEIGHT: u32 = 480;

// Framebuffer that implements DrawTarget
struct Framebuffer {
    pixels: Vec<u16>,
    width: u32,
    height: u32,
}

impl Framebuffer {
    fn new(width: u32, height: u32) -> Self {
        Self {
            pixels: vec![0; (width * height) as usize],
            width,
            height,
        }
    }

    fn save_png(&self, path: &Path) -> Result<(), Box<dyn std::error::Error>> {
        let mut img = ImageBuffer::<Rgb<u8>, Vec<u8>>::new(self.width, self.height);

        for y in 0..self.height {
            for x in 0..self.width {
                let idx = (y * self.width + x) as usize;
                let rgb565 = self.pixels[idx];

                // Convert RGB565 to RGB888
                let r = ((rgb565 >> 11) & 0x1F) as u8;
                let g = ((rgb565 >> 5) & 0x3F) as u8;
                let b = (rgb565 & 0x1F) as u8;

                // Scale up to 8-bit
                let r8 = (r << 3) | (r >> 2);
                let g8 = (g << 2) | (g >> 4);
                let b8 = (b << 3) | (b >> 2);

                img.put_pixel(x, y, Rgb([r8, g8, b8]));
            }
        }

        img.save(path)?;
        Ok(())
    }
}

impl DrawTarget for Framebuffer {
    type Color = Rgb565;
    type Error = core::convert::Infallible;

    fn draw_iter<I>(&mut self, pixels: I) -> Result<(), Self::Error>
    where
        I: IntoIterator<Item = Pixel<Self::Color>>,
    {
        for Pixel(coord, color) in pixels {
            if coord.x >= 0
                && coord.y >= 0
                && (coord.x as u32) < self.width
                && (coord.y as u32) < self.height
            {
                let idx = (coord.y as u32 * self.width + coord.x as u32) as usize;
                self.pixels[idx] = color.into_storage();
            }
        }
        Ok(())
    }
}

impl OriginDimensions for Framebuffer {
    fn size(&self) -> Size {
        Size::new(self.width, self.height)
    }
}

// Theme colors
#[derive(Clone, Copy)]
struct Theme {
    bg: Rgb565,
    card_bg: Rgb565,
    primary: Rgb565,
    text_primary: Rgb565,
    text_secondary: Rgb565,
    success: Rgb565,
    warning: Rgb565,
    error: Rgb565,
    disabled: Rgb565,
    status_bar_bg: Rgb565,
    border: Rgb565,
}

fn dark_theme() -> Theme {
    Theme {
        // Modern dark theme - neutral grays with blue accent
        bg: Rgb565::new(0x02, 0x04, 0x03),           // #111827 - slate-900
        card_bg: Rgb565::new(0x03, 0x06, 0x05),      // #1f2937 - slate-800
        primary: Rgb565::new(0x07, 0x2d, 0x1d),      // #3b82f6 - blue-500
        text_primary: Rgb565::new(0x1e, 0x3e, 0x1e), // #f9fafb - gray-50
        text_secondary: Rgb565::new(0x12, 0x24, 0x12), // #9ca3af - gray-400
        success: Rgb565::new(0x04, 0x2e, 0x0a),      // #22c55e - green-500
        warning: Rgb565::new(0x1e, 0x35, 0x02),      // #eab308 - yellow-500
        error: Rgb565::new(0x1d, 0x0b, 0x0b),        // #ef4444 - red-500
        disabled: Rgb565::new(0x06, 0x0c, 0x08),     // #374151 - gray-700
        status_bar_bg: Rgb565::new(0x01, 0x03, 0x02), // #0f172a - slate-950
        border: Rgb565::new(0x06, 0x0c, 0x08),       // #374151 - gray-700
    }
}

fn light_theme() -> Theme {
    Theme {
        // Clean light theme - white/gray with blue accent
        bg: Rgb565::new(0x1e, 0x3e, 0x1f),           // #f3f4f6 - gray-100
        card_bg: Rgb565::WHITE,                      // #ffffff
        primary: Rgb565::new(0x05, 0x25, 0x19),      // #2563eb - blue-600
        text_primary: Rgb565::new(0x02, 0x05, 0x03), // #111827 - gray-900
        text_secondary: Rgb565::new(0x0b, 0x16, 0x0b), // #6b7280 - gray-500
        success: Rgb565::new(0x03, 0x26, 0x08),      // #16a34a - green-600
        warning: Rgb565::new(0x1c, 0x2a, 0x01),      // #ca8a04 - yellow-600
        error: Rgb565::new(0x1b, 0x08, 0x08),        // #dc2626 - red-600
        disabled: Rgb565::new(0x17, 0x2f, 0x18),     // #d1d5db - gray-300
        status_bar_bg: Rgb565::WHITE,                // #ffffff
        border: Rgb565::new(0x17, 0x2f, 0x18),       // #e5e7eb - gray-200
    }
}

struct AppState {
    weight: f32,
    weight_stable: bool,
    wifi_connected: bool,
    server_connected: bool,
    brightness: u8,
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            weight: 1234.5,
            weight_stable: true,
            wifi_connected: true,
            server_connected: true,
            brightness: 80,
        }
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let output_dir = Path::new("screenshots");
    std::fs::create_dir_all(output_dir)?;

    // Load icons
    println!("Loading icons...");
    let icons = load_icons();
    if icons.filament.is_some() {
        println!("  Loaded filament icon");
    }
    if icons.ams_icon.is_some() {
        println!("  Loaded AMS icon");
    }

    let state = AppState::default();

    println!();
    println!("SpoolBuddy GUI Screenshot Generator");
    println!("====================================");
    println!();

    // Generate screenshots for each screen in both themes
    let screens = [
        ("home", render_home as fn(&mut Framebuffer, &AppState, &Theme, &IconSet)),
        ("spool_info", render_spool_info),
        ("settings", render_settings),
        ("ams_select", render_ams_select),
        ("calibration", render_calibration),
        ("wifi_setup", render_wifi_setup),
    ];

    for (name, render_fn) in &screens {
        println!("Rendering {}...", name);
        // Dark theme
        let mut fb = Framebuffer::new(DISPLAY_WIDTH, DISPLAY_HEIGHT);
        render_fn(&mut fb, &state, &dark_theme(), &icons);
        let path = output_dir.join(format!("{}_dark.png", name));
        fb.save_png(&path)?;
        println!("  Generated: {}", path.display());

        // Light theme
        let mut fb = Framebuffer::new(DISPLAY_WIDTH, DISPLAY_HEIGHT);
        render_fn(&mut fb, &state, &light_theme(), &icons);
        let path = output_dir.join(format!("{}_light.png", name));
        fb.save_png(&path)?;
        println!("  Generated: {}", path.display());
    }

    println!();
    println!("Done! Screenshots saved to ./screenshots/");
    Ok(())
}

fn render_status_bar(fb: &mut Framebuffer, title: &str, state: &AppState, theme: &Theme) {
    // Background
    let _ = Rectangle::new(Point::zero(), Size::new(DISPLAY_WIDTH, 40))
        .into_styled(PrimitiveStyle::with_fill(theme.status_bar_bg))
        .draw(fb);

    // Title
    let title_style = MonoTextStyle::new(&FONT_6X10, theme.text_primary);
    let _ = Text::new(title, Point::new(16, 24), title_style).draw(fb);

    // Server indicator
    let server_color = if state.server_connected { theme.success } else { theme.error };
    let _ = Circle::new(Point::new(DISPLAY_WIDTH as i32 - 50, 14), 12)
        .into_styled(PrimitiveStyle::with_fill(server_color))
        .draw(fb);

    // WiFi indicator (simplified bars)
    let wifi_x = DISPLAY_WIDTH as i32 - 80;
    for i in 0..4 {
        let bar_height = 4 + i * 3;
        let color = if state.wifi_connected && i < 3 { theme.primary } else { theme.disabled };
        let _ = Rectangle::new(
            Point::new(wifi_x + i * 5, 28 - bar_height),
            Size::new(4, bar_height as u32),
        )
        .into_styled(PrimitiveStyle::with_fill(color))
        .draw(fb);
    }
}

fn render_home(fb: &mut Framebuffer, state: &AppState, theme: &Theme, icons: &IconSet) {
    // Clear background
    let _ = Rectangle::new(Point::zero(), Size::new(DISPLAY_WIDTH, DISPLAY_HEIGHT))
        .into_styled(PrimitiveStyle::with_fill(theme.bg))
        .draw(fb);

    render_status_bar(fb, "SpoolBuddy", state, theme);

    // Main prompt card - larger, more rounded
    let card_w = 560;
    let card_h = 200;
    let card_x = (DISPLAY_WIDTH as i32 - card_w) / 2;
    let card_y = 70;

    let _ = RoundedRectangle::with_equal_corners(
        Rectangle::new(Point::new(card_x, card_y), Size::new(card_w as u32, card_h as u32)),
        Size::new(24, 24),
    )
    .into_styled(PrimitiveStyle::with_fill(theme.card_bg))
    .draw(fb);

    // Prompt text - centered
    let text_style = MonoTextStyle::new(&FONT_10X20, theme.text_secondary);
    let _ = Text::with_alignment(
        "Place Spool on Scale",
        Point::new(card_x + card_w / 2, card_y + 70),
        text_style,
        Alignment::Center,
    )
    .draw(fb);

    // Filament icon from OrcaSlicer assets (or fallback to geometric)
    let icon_cx = card_x + card_w / 2;
    let icon_y = card_y + 100;

    if let Some(ref filament_icon) = icons.filament {
        // Draw the loaded filament icon
        let ix = icon_cx - (filament_icon.width as i32 / 2);
        let iy = icon_y;
        filament_icon.draw(fb, ix, iy);
    } else {
        // Fallback: geometric NFC icon
        let _ = RoundedRectangle::with_equal_corners(
            Rectangle::new(Point::new(icon_cx - 25, icon_y), Size::new(50, 35)),
            Size::new(6, 6),
        )
        .into_styled(PrimitiveStyle::with_stroke(theme.primary, 2))
        .draw(fb);

        for i in 0..3 {
            let offset = i * 10 + 8;
            let _ = Circle::new(Point::new(icon_cx + 20 + offset - 8, icon_y + 17 - 8), 16 + i as u32 * 6)
                .into_styled(PrimitiveStyle::with_stroke(theme.primary, 2))
                .draw(fb);
        }
    }

    // Weight display - clean card
    let weight_y = 295;
    let weight_w = 340;
    let weight_h = 70;
    let weight_x = (DISPLAY_WIDTH as i32 - weight_w) / 2;

    let _ = RoundedRectangle::with_equal_corners(
        Rectangle::new(Point::new(weight_x, weight_y), Size::new(weight_w as u32, weight_h as u32)),
        Size::new(16, 16),
    )
    .into_styled(PrimitiveStyle::with_fill(theme.card_bg))
    .draw(fb);

    let weight_text = format!("{:.1} g", state.weight);
    let weight_style = MonoTextStyle::new(&FONT_10X20, theme.text_primary);
    let _ = Text::with_alignment(
        &weight_text,
        Point::new(weight_x + weight_w / 2 - 15, weight_y + 42),
        weight_style,
        Alignment::Center,
    )
    .draw(fb);

    // Stability indicator - smaller, on the right
    let indicator_color = if state.weight_stable { theme.success } else { theme.warning };
    let _ = Circle::new(Point::new(weight_x + weight_w - 45, weight_y + 27), 16)
        .into_styled(PrimitiveStyle::with_fill(indicator_color))
        .draw(fb);

    // Bottom buttons - more rounded, better spacing
    let btn_y = DISPLAY_HEIGHT as i32 - 70;
    let btn_h = 52;
    let btn_w = 160;

    // Tare button - outlined style
    let _ = RoundedRectangle::with_equal_corners(
        Rectangle::new(Point::new(32, btn_y), Size::new(btn_w as u32, btn_h as u32)),
        Size::new(12, 12),
    )
    .into_styled(PrimitiveStyle::with_stroke(theme.border, 2))
    .draw(fb);
    let _ = Text::with_alignment(
        "Tare",
        Point::new(32 + btn_w / 2, btn_y + 33),
        MonoTextStyle::new(&FONT_10X20, theme.text_primary),
        Alignment::Center,
    )
    .draw(fb);

    // Settings button - filled primary style
    let settings_x = DISPLAY_WIDTH as i32 - 32 - btn_w;
    let _ = RoundedRectangle::with_equal_corners(
        Rectangle::new(Point::new(settings_x, btn_y), Size::new(btn_w as u32, btn_h as u32)),
        Size::new(12, 12),
    )
    .into_styled(PrimitiveStyle::with_fill(theme.primary))
    .draw(fb);
    let _ = Text::with_alignment(
        "Settings",
        Point::new(settings_x + btn_w / 2, btn_y + 33),
        MonoTextStyle::new(&FONT_10X20, theme.card_bg),
        Alignment::Center,
    )
    .draw(fb);
}

fn render_spool_info(fb: &mut Framebuffer, state: &AppState, theme: &Theme, _icons: &IconSet) {
    let _ = Rectangle::new(Point::zero(), Size::new(DISPLAY_WIDTH, DISPLAY_HEIGHT))
        .into_styled(PrimitiveStyle::with_fill(theme.bg))
        .draw(fb);

    render_status_bar(fb, "SpoolBuddy", state, theme);

    // Spool card - larger, more rounded
    let card_x = 24;
    let card_y = 56;
    let card_w = DISPLAY_WIDTH as i32 - 48;
    let card_h = 140;

    let _ = RoundedRectangle::with_equal_corners(
        Rectangle::new(Point::new(card_x, card_y), Size::new(card_w as u32, card_h as u32)),
        Size::new(20, 20),
    )
    .into_styled(PrimitiveStyle::with_fill(theme.card_bg))
    .draw(fb);

    // Color swatch (jade green) - larger
    let swatch_color = Rgb565::new(0x02, 0x30, 0x10); // More muted jade
    let _ = RoundedRectangle::with_equal_corners(
        Rectangle::new(Point::new(card_x + 20, card_y + 20), Size::new(80, 80)),
        Size::new(12, 12),
    )
    .into_styled(PrimitiveStyle::with_fill(swatch_color))
    .draw(fb);

    let text_x = card_x + 120;
    let title_style = MonoTextStyle::new(&FONT_10X20, theme.text_primary);
    let subtitle_style = MonoTextStyle::new(&FONT_6X10, theme.text_secondary);

    let _ = Text::new("Bambu Lab PLA Basic", Point::new(text_x, card_y + 36), title_style).draw(fb);
    let _ = Text::new("Jade White", Point::new(text_x, card_y + 56), subtitle_style).draw(fb);

    // Progress bar - smoother
    let progress_y = card_y + 72;
    let progress_w = 360;
    let progress = 85;

    let _ = RoundedRectangle::with_equal_corners(
        Rectangle::new(Point::new(text_x, progress_y), Size::new(progress_w, 14)),
        Size::new(7, 7),
    )
    .into_styled(PrimitiveStyle::with_fill(theme.disabled))
    .draw(fb);

    let fill_w = (progress_w as u32 * progress / 100) as u32;
    let _ = RoundedRectangle::with_equal_corners(
        Rectangle::new(Point::new(text_x, progress_y), Size::new(fill_w, 14)),
        Size::new(7, 7),
    )
    .into_styled(PrimitiveStyle::with_fill(theme.success))
    .draw(fb);

    let _ = Text::new("85%", Point::new(text_x + progress_w as i32 + 12, progress_y + 11), subtitle_style).draw(fb);
    let _ = Text::new("850g / 1000g remaining", Point::new(text_x, card_y + 110), subtitle_style).draw(fb);
    let _ = Text::new("K: 0.022", Point::new(text_x + 200, card_y + 110), MonoTextStyle::new(&FONT_6X10, theme.primary)).draw(fb);

    // Source badge - more rounded
    let badge_x = card_x + card_w - 72;
    let _ = RoundedRectangle::with_equal_corners(
        Rectangle::new(Point::new(badge_x, card_y + 16), Size::new(56, 22)),
        Size::new(11, 11),
    )
    .into_styled(PrimitiveStyle::with_fill(theme.primary))
    .draw(fb);
    let _ = Text::new("BAMBU", Point::new(badge_x + 6, card_y + 31), MonoTextStyle::new(&FONT_6X10, theme.card_bg)).draw(fb);

    // Weight display - cleaner
    let weight_y = 215;
    let weight_w = 380;
    let weight_h = 75;
    let weight_x = (DISPLAY_WIDTH as i32 - weight_w) / 2;

    let _ = RoundedRectangle::with_equal_corners(
        Rectangle::new(Point::new(weight_x, weight_y), Size::new(weight_w as u32, weight_h as u32)),
        Size::new(16, 16),
    )
    .into_styled(PrimitiveStyle::with_fill(theme.card_bg))
    .draw(fb);

    let weight_text = format!("{:.1} g", state.weight);
    let _ = Text::with_alignment(&weight_text, Point::new(weight_x + weight_w / 2 - 10, weight_y + 48), title_style, Alignment::Center).draw(fb);

    let indicator_color = if state.weight_stable { theme.success } else { theme.warning };
    let _ = Circle::new(Point::new(weight_x + weight_w - 45, weight_y + 30), 16)
        .into_styled(PrimitiveStyle::with_fill(indicator_color))
        .draw(fb);

    // Action buttons - better styled
    let btn_y = DISPLAY_HEIGHT as i32 - 75;
    let btn_h = 54;
    let btn_w = 170;
    let btn_spacing = 12;
    let total_width = btn_w * 4 + btn_spacing * 3;
    let start_x = (DISPLAY_WIDTH as i32 - total_width) / 2;

    let buttons = ["Assign AMS", "Update", "Write Tag", "Details"];
    for (i, label) in buttons.iter().enumerate() {
        let x = start_x + (btn_w + btn_spacing) * i as i32;
        let (fill, stroke, text_color) = if i == 0 {
            (Some(theme.primary), None, theme.card_bg)
        } else {
            (None, Some(theme.border), theme.text_primary)
        };

        if let Some(fill_color) = fill {
            let _ = RoundedRectangle::with_equal_corners(
                Rectangle::new(Point::new(x, btn_y), Size::new(btn_w as u32, btn_h as u32)),
                Size::new(12, 12),
            )
            .into_styled(PrimitiveStyle::with_fill(fill_color))
            .draw(fb);
        }
        if let Some(stroke_color) = stroke {
            let _ = RoundedRectangle::with_equal_corners(
                Rectangle::new(Point::new(x, btn_y), Size::new(btn_w as u32, btn_h as u32)),
                Size::new(12, 12),
            )
            .into_styled(PrimitiveStyle::with_stroke(stroke_color, 2))
            .draw(fb);
        }

        let _ = Text::with_alignment(label, Point::new(x + btn_w / 2, btn_y + 34), MonoTextStyle::new(&FONT_6X10, text_color), Alignment::Center).draw(fb);
    }
}

fn render_settings(fb: &mut Framebuffer, state: &AppState, theme: &Theme, _icons: &IconSet) {
    let _ = Rectangle::new(Point::zero(), Size::new(DISPLAY_WIDTH, DISPLAY_HEIGHT))
        .into_styled(PrimitiveStyle::with_fill(theme.bg))
        .draw(fb);

    // Header
    let _ = Rectangle::new(Point::zero(), Size::new(DISPLAY_WIDTH, 50))
        .into_styled(PrimitiveStyle::with_fill(theme.status_bar_bg))
        .draw(fb);

    // Back arrow
    let arrow_style = PrimitiveStyle::with_stroke(theme.text_primary, 2);
    let _ = Line::new(Point::new(28, 25), Point::new(16, 25)).into_styled(arrow_style).draw(fb);
    let _ = Line::new(Point::new(16, 25), Point::new(22, 19)).into_styled(arrow_style).draw(fb);
    let _ = Line::new(Point::new(16, 25), Point::new(22, 31)).into_styled(arrow_style).draw(fb);

    let _ = Text::new("Settings", Point::new(52, 32), MonoTextStyle::new(&FONT_10X20, theme.text_primary)).draw(fb);

    let mut y = 70;
    let section_style = MonoTextStyle::new(&FONT_10X20, theme.text_primary);
    let label_style = MonoTextStyle::new(&FONT_6X10, theme.text_secondary);
    let value_style = MonoTextStyle::new(&FONT_6X10, theme.text_primary);

    // WiFi section
    let _ = Text::new("WiFi", Point::new(16, y), section_style).draw(fb);
    let _ = Rectangle::new(Point::new(16, y + 8), Size::new(DISPLAY_WIDTH - 32, 1))
        .into_styled(PrimitiveStyle::with_fill(theme.border))
        .draw(fb);
    y += 24;

    let _ = Text::new("├─ Network:", Point::new(20, y), label_style).draw(fb);
    let wifi_status = if state.wifi_connected { "NYHC! (Connected)" } else { "Not connected" };
    let _ = Text::new(wifi_status, Point::new(DISPLAY_WIDTH as i32 - 16 - wifi_status.len() as i32 * 6, y), value_style).draw(fb);
    y += 40;

    // Server section
    let _ = Text::new("Server", Point::new(16, y), section_style).draw(fb);
    let _ = Rectangle::new(Point::new(16, y + 8), Size::new(DISPLAY_WIDTH - 32, 1))
        .into_styled(PrimitiveStyle::with_fill(theme.border))
        .draw(fb);
    y += 24;

    let _ = Text::new("├─ URL:", Point::new(20, y), label_style).draw(fb);
    let _ = Text::new("spoolbuddy.local:3000", Point::new(DISPLAY_WIDTH as i32 - 16 - 21 * 6, y), value_style).draw(fb);
    y += 20;

    let _ = Text::new("└─ Status:", Point::new(20, y), label_style).draw(fb);
    let server_status = if state.server_connected { "Connected" } else { "Disconnected" };
    let status_color = if state.server_connected { theme.success } else { theme.error };
    let _ = Text::new(server_status, Point::new(DISPLAY_WIDTH as i32 - 16 - server_status.len() as i32 * 6, y), MonoTextStyle::new(&FONT_6X10, status_color)).draw(fb);
    y += 32;

    // Display section
    let _ = Text::new("Display", Point::new(16, y), section_style).draw(fb);
    let _ = Rectangle::new(Point::new(16, y + 8), Size::new(DISPLAY_WIDTH - 32, 1))
        .into_styled(PrimitiveStyle::with_fill(theme.border))
        .draw(fb);
    y += 24;

    let _ = Text::new("Brightness", Point::new(36, y + 8), label_style).draw(fb);
    let slider_x = 120;
    let slider_w = 200;

    let _ = RoundedRectangle::with_equal_corners(
        Rectangle::new(Point::new(slider_x, y + 2), Size::new(slider_w, 12)),
        Size::new(6, 6),
    )
    .into_styled(PrimitiveStyle::with_fill(theme.disabled))
    .draw(fb);

    let fill_w = (slider_w as u32 * state.brightness as u32 / 100) as u32;
    let _ = RoundedRectangle::with_equal_corners(
        Rectangle::new(Point::new(slider_x, y + 2), Size::new(fill_w, 12)),
        Size::new(6, 6),
    )
    .into_styled(PrimitiveStyle::with_fill(theme.primary))
    .draw(fb);

    let _ = Text::new(&format!("{}%", state.brightness), Point::new(slider_x + slider_w as i32 + 8, y + 12), value_style).draw(fb);
    y += 40;

    // About section
    let _ = Text::new("About", Point::new(16, y), section_style).draw(fb);
    let _ = Rectangle::new(Point::new(16, y + 8), Size::new(DISPLAY_WIDTH - 32, 1))
        .into_styled(PrimitiveStyle::with_fill(theme.border))
        .draw(fb);
    y += 24;

    let _ = Text::new("├─ Firmware:", Point::new(20, y), label_style).draw(fb);
    let _ = Text::new("v0.1.0", Point::new(DISPLAY_WIDTH as i32 - 16 - 6 * 6, y), value_style).draw(fb);
    y += 20;

    let _ = Text::new("└─ Device ID:", Point::new(20, y), label_style).draw(fb);
    let _ = Text::new("SPOOLBUDDY-A1B2C3", Point::new(DISPLAY_WIDTH as i32 - 16 - 17 * 6, y), value_style).draw(fb);
}

fn render_ams_select(fb: &mut Framebuffer, _state: &AppState, theme: &Theme, icons: &IconSet) {
    let _ = Rectangle::new(Point::zero(), Size::new(DISPLAY_WIDTH, DISPLAY_HEIGHT))
        .into_styled(PrimitiveStyle::with_fill(theme.bg))
        .draw(fb);

    // Header
    let _ = Rectangle::new(Point::zero(), Size::new(DISPLAY_WIDTH, 50))
        .into_styled(PrimitiveStyle::with_fill(theme.status_bar_bg))
        .draw(fb);

    let arrow_style = PrimitiveStyle::with_stroke(theme.text_primary, 2);
    let _ = Line::new(Point::new(28, 25), Point::new(16, 25)).into_styled(arrow_style).draw(fb);
    let _ = Line::new(Point::new(16, 25), Point::new(22, 19)).into_styled(arrow_style).draw(fb);
    let _ = Line::new(Point::new(16, 25), Point::new(22, 31)).into_styled(arrow_style).draw(fb);

    let _ = Text::new("Select AMS Slot", Point::new(52, 32), MonoTextStyle::new(&FONT_10X20, theme.text_primary)).draw(fb);

    let mut y = 70;
    let label_style = MonoTextStyle::new(&FONT_6X10, theme.text_secondary);

    let _ = Text::new("X1 Carbon (00M09A...)", Point::new(16, y), label_style).draw(fb);
    y += 24;

    // AMS card
    let _ = RoundedRectangle::with_equal_corners(
        Rectangle::new(Point::new(16, y), Size::new(DISPLAY_WIDTH - 32, 130)),
        Size::new(8, 8),
    )
    .into_styled(PrimitiveStyle::with_fill(theme.card_bg))
    .draw(fb);

    let _ = Text::new("AMS A", Point::new(28, y + 20), label_style).draw(fb);

    // 4 slots
    let slot_size = 70;
    let slot_spacing = 16;
    let slots_start_x = 28;
    let slots_y = y + 36;

    let slot_data = [
        ("A1", "PLA", Rgb565::new(0x00, 0x38, 0x10), 85),
        ("A2", "PETG", Rgb565::new(0x00, 0x18, 0x38), 60),
        ("A3", "", Rgb565::new(0x08, 0x08, 0x08), 0),
        ("A4", "PLA", Rgb565::new(0x38, 0x00, 0x00), 40),
    ];

    for (i, (label, material, color, percent)) in slot_data.iter().enumerate() {
        let x = slots_start_x + (slot_size + slot_spacing) * i as i32;

        let _ = RoundedRectangle::with_equal_corners(
            Rectangle::new(Point::new(x, slots_y), Size::new(slot_size as u32, slot_size as u32)),
            Size::new(4, 4),
        )
        .into_styled(PrimitiveStyle::with_stroke(theme.border, 2))
        .draw(fb);

        if *percent > 0 {
            let fill_h = (slot_size - 4) * percent / 100;
            let fill_y = slots_y + slot_size - 2 - fill_h;
            let _ = RoundedRectangle::with_equal_corners(
                Rectangle::new(Point::new(x + 2, fill_y), Size::new(slot_size as u32 - 4, fill_h as u32)),
                Size::new(2, 2),
            )
            .into_styled(PrimitiveStyle::with_fill(*color))
            .draw(fb);
        }

        let _ = Text::with_alignment(label, Point::new(x + slot_size / 2, slots_y + 24), MonoTextStyle::new(&FONT_6X10, theme.text_primary), Alignment::Center).draw(fb);

        if !material.is_empty() {
            let _ = Text::with_alignment(material, Point::new(x + slot_size / 2, slots_y + 50), MonoTextStyle::new(&FONT_6X10, theme.text_secondary), Alignment::Center).draw(fb);
        }
    }

    y += 150;

    // External section
    let _ = RoundedRectangle::with_equal_corners(
        Rectangle::new(Point::new(16, y), Size::new(DISPLAY_WIDTH - 32, 100)),
        Size::new(8, 8),
    )
    .into_styled(PrimitiveStyle::with_fill(theme.card_bg))
    .draw(fb);

    let _ = Text::new("External Spool", Point::new(28, y + 20), label_style).draw(fb);

    let _ = RoundedRectangle::with_equal_corners(
        Rectangle::new(Point::new(28, y + 36), Size::new(slot_size as u32, slot_size as u32)),
        Size::new(4, 4),
    )
    .into_styled(PrimitiveStyle::with_stroke(theme.border, 2))
    .draw(fb);
    let _ = Text::with_alignment("EXT", Point::new(28 + slot_size / 2, y + 36 + 40), MonoTextStyle::new(&FONT_6X10, theme.text_primary), Alignment::Center).draw(fb);

    // Cancel button
    let btn_y = DISPLAY_HEIGHT as i32 - 60;
    let _ = RoundedRectangle::with_equal_corners(
        Rectangle::new(Point::new(DISPLAY_WIDTH as i32 - 16 - 100, btn_y), Size::new(100, 44)),
        Size::new(4, 4),
    )
    .into_styled(PrimitiveStyle::with_stroke(theme.border, 2))
    .draw(fb);
    let _ = Text::with_alignment("CANCEL", Point::new(DISPLAY_WIDTH as i32 - 16 - 50, btn_y + 28), MonoTextStyle::new(&FONT_6X10, theme.text_primary), Alignment::Center).draw(fb);
}

fn render_calibration(fb: &mut Framebuffer, state: &AppState, theme: &Theme, _icons: &IconSet) {
    let _ = Rectangle::new(Point::zero(), Size::new(DISPLAY_WIDTH, DISPLAY_HEIGHT))
        .into_styled(PrimitiveStyle::with_fill(theme.bg))
        .draw(fb);

    let _ = Rectangle::new(Point::zero(), Size::new(DISPLAY_WIDTH, 50))
        .into_styled(PrimitiveStyle::with_fill(theme.status_bar_bg))
        .draw(fb);

    let _ = Text::new("Scale Calibration (1/2)", Point::new(16, 32), MonoTextStyle::new(&FONT_10X20, theme.text_primary)).draw(fb);

    let card_x = 40;
    let card_y = 70;
    let card_w = DISPLAY_WIDTH as i32 - 80;
    let card_h = 280;

    let _ = RoundedRectangle::with_equal_corners(
        Rectangle::new(Point::new(card_x, card_y), Size::new(card_w as u32, card_h as u32)),
        Size::new(12, 12),
    )
    .into_styled(PrimitiveStyle::with_fill(theme.card_bg))
    .draw(fb);

    // Scale icon
    let icon_x = card_x + card_w / 2 - 30;
    let icon_y = card_y + 30;
    let _ = Rectangle::new(Point::new(icon_x, icon_y + 40), Size::new(60, 6))
        .into_styled(PrimitiveStyle::with_fill(theme.primary))
        .draw(fb);
    let _ = Rectangle::new(Point::new(icon_x + 8, icon_y), Size::new(44, 36))
        .into_styled(PrimitiveStyle::with_stroke(theme.primary, 2))
        .draw(fb);

    let title_style = MonoTextStyle::new(&FONT_10X20, theme.text_primary);
    let label_style = MonoTextStyle::new(&FONT_6X10, theme.text_secondary);

    let _ = Text::new("Remove everything from", Point::new(card_x + 24, card_y + 120), title_style).draw(fb);
    let _ = Text::new("the scale", Point::new(card_x + 24, card_y + 144), title_style).draw(fb);

    let _ = Text::new("Current reading:", Point::new(card_x + 24, card_y + 190), label_style).draw(fb);

    let weight_text = format!("{:.1} g", state.weight);
    let _ = Text::new(&weight_text, Point::new(card_x + 24, card_y + 220), MonoTextStyle::new(&FONT_10X20, theme.primary)).draw(fb);

    if state.weight_stable {
        let _ = Text::new("(stable)", Point::new(card_x + 150, card_y + 220), MonoTextStyle::new(&FONT_6X10, theme.success)).draw(fb);
    }

    let btn_y = DISPLAY_HEIGHT as i32 - 70;
    let btn_h = 48;
    let btn_w = 140;

    let _ = RoundedRectangle::with_equal_corners(
        Rectangle::new(Point::new(card_x + 16, btn_y), Size::new(btn_w as u32, btn_h as u32)),
        Size::new(4, 4),
    )
    .into_styled(PrimitiveStyle::with_fill(theme.primary))
    .draw(fb);
    let _ = Text::with_alignment("NEXT", Point::new(card_x + 16 + btn_w / 2, btn_y + 32), MonoTextStyle::new(&FONT_10X20, theme.bg), Alignment::Center).draw(fb);

    let _ = RoundedRectangle::with_equal_corners(
        Rectangle::new(Point::new(card_x + card_w - 16 - btn_w, btn_y), Size::new(btn_w as u32, btn_h as u32)),
        Size::new(4, 4),
    )
    .into_styled(PrimitiveStyle::with_stroke(theme.border, 2))
    .draw(fb);
    let _ = Text::with_alignment("CANCEL", Point::new(card_x + card_w - 16 - btn_w / 2, btn_y + 32), MonoTextStyle::new(&FONT_10X20, theme.text_primary), Alignment::Center).draw(fb);
}

fn render_wifi_setup(fb: &mut Framebuffer, _state: &AppState, theme: &Theme, _icons: &IconSet) {
    let _ = Rectangle::new(Point::zero(), Size::new(DISPLAY_WIDTH, DISPLAY_HEIGHT))
        .into_styled(PrimitiveStyle::with_fill(theme.bg))
        .draw(fb);

    let _ = Rectangle::new(Point::zero(), Size::new(DISPLAY_WIDTH, 50))
        .into_styled(PrimitiveStyle::with_fill(theme.status_bar_bg))
        .draw(fb);

    let _ = Text::new("WiFi Setup", Point::new(16, 32), MonoTextStyle::new(&FONT_10X20, theme.text_primary)).draw(fb);

    let mut y = 70;
    let title_style = MonoTextStyle::new(&FONT_10X20, theme.text_primary);
    let label_style = MonoTextStyle::new(&FONT_6X10, theme.text_secondary);

    let _ = Text::new("Connect to SpoolBuddy WiFi:", Point::new(16, y), label_style).draw(fb);
    y += 20;

    let _ = RoundedRectangle::with_equal_corners(
        Rectangle::new(Point::new(16, y), Size::new(DISPLAY_WIDTH - 32, 80)),
        Size::new(8, 8),
    )
    .into_styled(PrimitiveStyle::with_fill(theme.card_bg))
    .draw(fb);

    let _ = Text::new("SSID: SpoolBuddy-Setup", Point::new(32, y + 28), title_style).draw(fb);
    let _ = Text::new("Password: spoolbuddy", Point::new(32, y + 56), label_style).draw(fb);
    y += 100;

    let _ = Text::new("Then open: http://192.168.4.1", Point::new(16, y), label_style).draw(fb);
    y += 30;

    let _ = Text::new("Or scan available networks:", Point::new(16, y), label_style).draw(fb);
    y += 20;

    let _ = RoundedRectangle::with_equal_corners(
        Rectangle::new(Point::new(16, y), Size::new(DISPLAY_WIDTH - 32, 150)),
        Size::new(8, 8),
    )
    .into_styled(PrimitiveStyle::with_fill(theme.card_bg))
    .draw(fb);

    let networks = [("NYHC!", 4), ("Neighbor-5G", 2), ("Guest-Network", 1)];

    for (i, (name, bars)) in networks.iter().enumerate() {
        let row_y = y + 16 + i as i32 * 44;

        let _ = Text::new(name, Point::new(32, row_y + 20), title_style).draw(fb);

        let bar_x = DISPLAY_WIDTH as i32 - 100;
        for b in 0..4i32 {
            let bar_h = 6 + b * 4;
            let color = if b < *bars { theme.primary } else { theme.disabled };
            let _ = Rectangle::new(Point::new(bar_x + b * 8, row_y + 24 - bar_h), Size::new(6, bar_h as u32))
                .into_styled(PrimitiveStyle::with_fill(color))
                .draw(fb);
        }

        if i < 2 {
            let _ = Rectangle::new(Point::new(32, row_y + 36), Size::new(DISPLAY_WIDTH - 80, 1))
                .into_styled(PrimitiveStyle::with_fill(theme.border))
                .draw(fb);
        }
    }

    let btn_y = DISPLAY_HEIGHT as i32 - 60;
    let _ = RoundedRectangle::with_equal_corners(
        Rectangle::new(Point::new(DISPLAY_WIDTH as i32 - 16 - 100, btn_y), Size::new(100, 44)),
        Size::new(4, 4),
    )
    .into_styled(PrimitiveStyle::with_stroke(theme.border, 2))
    .draw(fb);
    let _ = Text::with_alignment("REFRESH", Point::new(DISPLAY_WIDTH as i32 - 16 - 50, btn_y + 28), MonoTextStyle::new(&FONT_6X10, theme.text_primary), Alignment::Center).draw(fb);
}
