//! RGB Parallel Display Driver for Waveshare ESP32-S3-Touch-LCD-4.3
//!
//! The display uses a 16-bit RGB565 parallel interface with:
//! - 800x480 resolution
//! - RGB565 color format (16-bit per pixel)
//! - DE (Data Enable) mode timing
//!
//! GPIO Mapping (Waveshare ESP32-S3-Touch-LCD-4.3):
//! - LCD_DE:    GPIO40
//! - LCD_VSYNC: GPIO41
//! - LCD_HSYNC: GPIO39
//! - LCD_PCLK:  GPIO42
//! - LCD_R0-R4: GPIO45, 48, 47, 21, 14
//! - LCD_G0-G5: GPIO9, 46, 3, 8, 18, 17
//! - LCD_B0-B4: GPIO10, 11, 12, 13, 14
//! - LCD_BL:    GPIO2 (Backlight PWM)

#![allow(dead_code)]

use super::{DisplayError, DISPLAY_HEIGHT, DISPLAY_WIDTH};
use embedded_graphics::pixelcolor::Rgb565;
use embedded_graphics::prelude::*;
use log::info;

/// Display timing configuration for 800x480 LCD
pub struct DisplayTiming {
    pub h_res: u16,
    pub v_res: u16,
    pub h_sync_width: u16,
    pub h_back_porch: u16,
    pub h_front_porch: u16,
    pub v_sync_width: u16,
    pub v_back_porch: u16,
    pub v_front_porch: u16,
    pub pclk_hz: u32,
}

impl Default for DisplayTiming {
    fn default() -> Self {
        // Standard timing for 800x480 @ 60Hz
        Self {
            h_res: 800,
            v_res: 480,
            h_sync_width: 4,
            h_back_porch: 8,
            h_front_porch: 8,
            v_sync_width: 4,
            v_back_porch: 8,
            v_front_porch: 8,
            pclk_hz: 21_000_000, // 21MHz pixel clock
        }
    }
}

/// Framebuffer size in bytes (RGB565 = 2 bytes per pixel)
pub const FRAMEBUFFER_SIZE: usize = (DISPLAY_WIDTH as usize) * (DISPLAY_HEIGHT as usize) * 2;

/// Display driver for the RGB parallel interface
pub struct Display {
    /// Double-buffered framebuffer pointers
    framebuffer: &'static mut [u8],
    /// Current backlight brightness (0-100)
    brightness: u8,
    /// Whether display is initialized
    initialized: bool,
}

impl Display {
    /// Create a new display driver
    ///
    /// # Safety
    /// The framebuffer must be allocated in PSRAM and persist for the lifetime of the display.
    pub unsafe fn new(framebuffer: &'static mut [u8]) -> Result<Self, DisplayError> {
        if framebuffer.len() < FRAMEBUFFER_SIZE {
            return Err(DisplayError::BufferOverflow);
        }

        Ok(Self {
            framebuffer,
            brightness: 80,
            initialized: false,
        })
    }

    /// Initialize the display hardware
    pub fn init(&mut self) -> Result<(), DisplayError> {
        info!("Initializing RGB parallel display (800x480)");

        // TODO: Configure GPIO pins for RGB parallel interface
        // This requires esp-hal LCD peripheral support

        // Configure timing
        let _timing = DisplayTiming::default();

        // TODO: Initialize LCD peripheral with timing config

        // Initialize backlight to default brightness
        self.set_backlight(self.brightness)?;

        // Clear framebuffer to black
        self.clear_buffer();

        self.initialized = true;
        info!("Display initialized");

        Ok(())
    }

    /// Set backlight brightness (0-100)
    pub fn set_backlight(&mut self, brightness: u8) -> Result<(), DisplayError> {
        self.brightness = brightness.min(100);

        // TODO: Configure PWM on GPIO2 for backlight control
        // PWM duty = brightness * 255 / 100

        info!("Backlight set to {}%", self.brightness);
        Ok(())
    }

    /// Get current backlight brightness
    pub fn backlight(&self) -> u8 {
        self.brightness
    }

    /// Clear the framebuffer to black
    pub fn clear_buffer(&mut self) {
        self.framebuffer[..FRAMEBUFFER_SIZE].fill(0);
    }

    /// Fill the framebuffer with a solid color
    pub fn fill(&mut self, color: Rgb565) {
        let color_bytes = color.into_storage().to_le_bytes();
        for chunk in self.framebuffer[..FRAMEBUFFER_SIZE].chunks_exact_mut(2) {
            chunk[0] = color_bytes[0];
            chunk[1] = color_bytes[1];
        }
    }

    /// Get a mutable reference to the framebuffer
    pub fn framebuffer_mut(&mut self) -> &mut [u8] {
        &mut self.framebuffer[..FRAMEBUFFER_SIZE]
    }

    /// Set a pixel in the framebuffer
    #[inline]
    pub fn set_pixel(&mut self, x: u32, y: u32, color: Rgb565) {
        if x < DISPLAY_WIDTH && y < DISPLAY_HEIGHT {
            let offset = ((y * DISPLAY_WIDTH + x) * 2) as usize;
            let color_bytes = color.into_storage().to_le_bytes();
            self.framebuffer[offset] = color_bytes[0];
            self.framebuffer[offset + 1] = color_bytes[1];
        }
    }

    /// Flush the framebuffer to the display
    ///
    /// For RGB parallel displays, this triggers a DMA transfer.
    pub fn flush(&mut self) -> Result<(), DisplayError> {
        if !self.initialized {
            return Err(DisplayError::InitFailed);
        }

        // TODO: Trigger DMA transfer to LCD peripheral
        // The ESP32-S3 LCD peripheral can continuously refresh from the framebuffer

        Ok(())
    }

    /// Check if display is initialized
    pub fn is_initialized(&self) -> bool {
        self.initialized
    }
}

/// Implement embedded-graphics DrawTarget for the display
impl DrawTarget for Display {
    type Color = Rgb565;
    type Error = DisplayError;

    fn draw_iter<I>(&mut self, pixels: I) -> Result<(), Self::Error>
    where
        I: IntoIterator<Item = Pixel<Self::Color>>,
    {
        for Pixel(coord, color) in pixels {
            if coord.x >= 0
                && coord.y >= 0
                && (coord.x as u32) < DISPLAY_WIDTH
                && (coord.y as u32) < DISPLAY_HEIGHT
            {
                self.set_pixel(coord.x as u32, coord.y as u32, color);
            }
        }
        Ok(())
    }
}

impl OriginDimensions for Display {
    fn size(&self) -> Size {
        Size::new(DISPLAY_WIDTH, DISPLAY_HEIGHT)
    }
}

/// Display configuration for initialization
#[derive(Clone)]
pub struct DisplayConfig {
    /// Initial backlight brightness (0-100)
    pub brightness: u8,
    /// Whether to use double buffering
    pub double_buffer: bool,
    /// Whether to invert colors
    pub invert_colors: bool,
    /// Pixel clock frequency in Hz
    pub pclk_hz: u32,
}

impl Default for DisplayConfig {
    fn default() -> Self {
        Self {
            brightness: 80,
            double_buffer: true,
            invert_colors: false,
            pclk_hz: 21_000_000,
        }
    }
}

/// GPIO pin assignments for the display
pub mod pins {
    /// Data Enable pin
    pub const DE: u8 = 40;
    /// Vertical Sync pin
    pub const VSYNC: u8 = 41;
    /// Horizontal Sync pin
    pub const HSYNC: u8 = 39;
    /// Pixel Clock pin
    pub const PCLK: u8 = 42;
    /// Backlight control pin (PWM)
    pub const BACKLIGHT: u8 = 2;

    /// Red data pins (R0-R4, 5 bits)
    pub const RED: [u8; 5] = [45, 48, 47, 21, 14];
    /// Green data pins (G0-G5, 6 bits)
    pub const GREEN: [u8; 6] = [9, 46, 3, 8, 18, 17];
    /// Blue data pins (B0-B4, 5 bits)
    pub const BLUE: [u8; 5] = [10, 11, 12, 13, 14];
}
