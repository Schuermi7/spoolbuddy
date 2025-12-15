//! UI module for the 4.3" 800x480 touch display.
//!
//! The Waveshare ESP32-S3-Touch-LCD-4.3 has:
//! - 800x480 RGB565 display (parallel RGB interface)
//! - GT911 capacitive touch controller (I2C)
//! - 5-point multi-touch support
//!
//! UI framework options:
//! - embedded-graphics: Simple 2D graphics
//! - LVGL: Full-featured GUI library
//! - Slint: Modern declarative UI (like SpoolEase uses)

use embedded_graphics::{
    mono_font::{ascii::FONT_10X20, MonoTextStyle},
    pixelcolor::Rgb565,
    prelude::*,
    primitives::{Circle, PrimitiveStyle, Rectangle},
    text::Text,
};
use log::info;

/// Display dimensions
pub const DISPLAY_WIDTH: u32 = 800;
pub const DISPLAY_HEIGHT: u32 = 480;

/// UI state
pub struct Ui {
    /// Current weight in grams
    weight: f32,
    /// Is weight stable?
    weight_stable: bool,
    /// Current tag info (if any)
    tag_info: Option<TagDisplay>,
    /// Connection status
    connected: bool,
    /// Server URL
    server_url: heapless::String<128>,
}

/// Tag information for display
pub struct TagDisplay {
    pub material: heapless::String<32>,
    pub color_name: heapless::String<32>,
    pub brand: heapless::String<32>,
    pub color_rgb: (u8, u8, u8),
}

impl Ui {
    pub fn new() -> Self {
        Self {
            weight: 0.0,
            weight_stable: false,
            tag_info: None,
            connected: false,
            server_url: heapless::String::new(),
        }
    }

    /// Update weight display.
    pub fn set_weight(&mut self, grams: f32, stable: bool) {
        self.weight = grams;
        self.weight_stable = stable;
    }

    /// Update tag info display.
    pub fn set_tag_info(&mut self, info: Option<TagDisplay>) {
        self.tag_info = info;
    }

    /// Update connection status.
    pub fn set_connected(&mut self, connected: bool) {
        self.connected = connected;
    }

    /// Render the UI to a display.
    ///
    /// This is a simplified stub - real implementation would use LVGL or similar.
    pub fn render<D>(&self, display: &mut D) -> Result<(), D::Error>
    where
        D: DrawTarget<Color = Rgb565>,
    {
        // Clear screen
        display.clear(Rgb565::BLACK)?;

        // Draw weight
        let weight_text = if self.weight_stable {
            // Show weight with checkmark for stable
            alloc::format!("{:.1}g ✓", self.weight)
        } else {
            alloc::format!("{:.1}g", self.weight)
        };

        let style = MonoTextStyle::new(&FONT_10X20, Rgb565::WHITE);
        Text::new(&weight_text, Point::new(20, 50), style).draw(display)?;

        // Draw tag info if present
        if let Some(ref tag) = self.tag_info {
            // Color swatch
            let color = Rgb565::new(
                tag.color_rgb.0 >> 3,
                tag.color_rgb.1 >> 2,
                tag.color_rgb.2 >> 3,
            );
            Rectangle::new(Point::new(20, 100), Size::new(60, 60))
                .into_styled(PrimitiveStyle::with_fill(color))
                .draw(display)?;

            // Material and brand
            let info_text = alloc::format!("{} - {}", tag.material, tag.brand);
            Text::new(&info_text, Point::new(100, 130), style).draw(display)?;

            // Color name
            Text::new(&tag.color_name, Point::new(100, 160), style).draw(display)?;
        } else {
            // No tag - show placeholder
            Text::new("Place spool on scale", Point::new(20, 130), style).draw(display)?;
        }

        // Connection indicator
        let conn_color = if self.connected {
            Rgb565::GREEN
        } else {
            Rgb565::RED
        };
        Circle::new(Point::new(DISPLAY_WIDTH as i32 - 30, 10), 15)
            .into_styled(PrimitiveStyle::with_fill(conn_color))
            .draw(display)?;

        Ok(())
    }
}

/// Touch event types
#[derive(Debug, Clone, Copy)]
pub enum TouchEvent {
    Press { x: u16, y: u16 },
    Release { x: u16, y: u16 },
    Move { x: u16, y: u16 },
}

/// Initialize the display hardware.
pub async fn init_display() -> Result<(), DisplayError> {
    info!("Initializing display (stub)");

    // TODO: Initialize RGB parallel interface
    // TODO: Configure display timing
    // TODO: Initialize backlight
    // TODO: Initialize GT911 touch controller

    Ok(())
}

/// Read touch events from GT911.
pub async fn read_touch() -> Result<Option<TouchEvent>, DisplayError> {
    // TODO: Read from GT911 via I2C
    Ok(None)
}

/// Display errors
#[derive(Debug, Clone, Copy)]
pub enum DisplayError {
    InitFailed,
    I2cError,
    InvalidConfig,
}
