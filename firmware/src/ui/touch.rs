//! GT911 Capacitive Touch Controller Driver
//!
//! The GT911 is a 5-point capacitive touch controller using I2C.
//!
//! GPIO Mapping (Waveshare ESP32-S3-Touch-LCD-4.3):
//! - I2C SDA: GPIO4
//! - I2C SCL: GPIO5
//! - INT:     GPIO1
//! - RST:     GPIO38
//!
//! The GT911 can operate at two I2C addresses:
//! - 0x5D (default when INT is HIGH during reset)
//! - 0x14 (when INT is LOW during reset)

#![allow(dead_code)]

use super::{DisplayError, TouchEvent, DISPLAY_HEIGHT, DISPLAY_WIDTH};
use embedded_hal::i2c::I2c;
use log::{debug, info, warn};

/// GT911 I2C address (default)
pub const GT911_ADDR: u8 = 0x5D;

/// GT911 alternate I2C address
pub const GT911_ADDR_ALT: u8 = 0x14;

/// GT911 register addresses
mod reg {
    pub const PRODUCT_ID: u16 = 0x8140;
    pub const FIRMWARE_VERSION: u16 = 0x8144;
    pub const X_RESOLUTION: u16 = 0x8146;
    pub const Y_RESOLUTION: u16 = 0x8148;
    pub const VENDOR_ID: u16 = 0x814A;
    pub const CONFIG_START: u16 = 0x8047;
    pub const CONFIG_VERSION: u16 = 0x8047;
    pub const COMMAND: u16 = 0x8040;
    pub const POINT_INFO: u16 = 0x814E;
    pub const POINT_1: u16 = 0x814F;
    pub const POINT_2: u16 = 0x8157;
    pub const POINT_3: u16 = 0x815F;
    pub const POINT_4: u16 = 0x8167;
    pub const POINT_5: u16 = 0x816F;
}

/// GT911 commands
mod cmd {
    pub const READ_COORD_STATUS: u8 = 0x00;
    pub const SOFT_RESET: u8 = 0x02;
    pub const UPDATE_CONFIG: u8 = 0x01;
}

/// Touch point data
#[derive(Debug, Clone, Copy, Default)]
pub struct TouchPoint {
    /// X coordinate (0-799 for 800px width)
    pub x: u16,
    /// Y coordinate (0-479 for 480px height)
    pub y: u16,
    /// Touch pressure/size
    pub size: u16,
    /// Track ID for multi-touch
    pub track_id: u8,
}

/// GT911 touch controller driver
pub struct Gt911<I2C> {
    i2c: I2C,
    addr: u8,
    /// Last known touch state
    last_touch: Option<TouchPoint>,
    /// X resolution from config
    x_resolution: u16,
    /// Y resolution from config
    y_resolution: u16,
}

impl<I2C, E> Gt911<I2C>
where
    I2C: I2c<Error = E>,
{
    /// Create a new GT911 driver
    pub fn new(i2c: I2C) -> Self {
        Self {
            i2c,
            addr: GT911_ADDR,
            last_touch: None,
            x_resolution: DISPLAY_WIDTH as u16,
            y_resolution: DISPLAY_HEIGHT as u16,
        }
    }

    /// Create with alternate I2C address
    pub fn new_with_addr(i2c: I2C, addr: u8) -> Self {
        Self {
            i2c,
            addr,
            last_touch: None,
            x_resolution: DISPLAY_WIDTH as u16,
            y_resolution: DISPLAY_HEIGHT as u16,
        }
    }

    /// Initialize the touch controller
    pub fn init(&mut self) -> Result<(), DisplayError> {
        info!("Initializing GT911 touch controller at 0x{:02X}", self.addr);

        // Read product ID to verify communication
        let product_id = self.read_product_id()?;
        info!("GT911 Product ID: {:?}", product_id);

        // Read firmware version
        let fw_version = self.read_firmware_version()?;
        info!("GT911 Firmware Version: 0x{:04X}", fw_version);

        // Read resolution from config
        let (x_res, y_res) = self.read_resolution()?;
        self.x_resolution = x_res;
        self.y_resolution = y_res;
        info!("GT911 Resolution: {}x{}", x_res, y_res);

        Ok(())
    }

    /// Read the product ID (should be "911" for GT911)
    pub fn read_product_id(&mut self) -> Result<[u8; 4], DisplayError> {
        let mut buf = [0u8; 4];
        self.read_register(reg::PRODUCT_ID, &mut buf)?;
        Ok(buf)
    }

    /// Read firmware version
    pub fn read_firmware_version(&mut self) -> Result<u16, DisplayError> {
        let mut buf = [0u8; 2];
        self.read_register(reg::FIRMWARE_VERSION, &mut buf)?;
        Ok(u16::from_le_bytes(buf))
    }

    /// Read configured resolution
    pub fn read_resolution(&mut self) -> Result<(u16, u16), DisplayError> {
        let mut x_buf = [0u8; 2];
        let mut y_buf = [0u8; 2];
        self.read_register(reg::X_RESOLUTION, &mut x_buf)?;
        self.read_register(reg::Y_RESOLUTION, &mut y_buf)?;
        Ok((u16::from_le_bytes(x_buf), u16::from_le_bytes(y_buf)))
    }

    /// Read touch points
    ///
    /// Returns the number of active touch points and their data.
    pub fn read_touch_points(&mut self) -> Result<(u8, [TouchPoint; 5]), DisplayError> {
        let mut points = [TouchPoint::default(); 5];

        // Read point info register
        let mut status = [0u8; 1];
        self.read_register(reg::POINT_INFO, &mut status)?;

        let status = status[0];
        let buffer_ready = (status & 0x80) != 0;
        let num_points = status & 0x0F;

        if !buffer_ready || num_points == 0 {
            // Clear the buffer ready flag
            self.write_register(reg::POINT_INFO, &[0])?;
            return Ok((0, points));
        }

        // Read touch point data (8 bytes per point)
        let point_regs = [
            reg::POINT_1,
            reg::POINT_2,
            reg::POINT_3,
            reg::POINT_4,
            reg::POINT_5,
        ];

        for i in 0..(num_points as usize).min(5) {
            let mut buf = [0u8; 8];
            self.read_register(point_regs[i], &mut buf)?;

            points[i] = TouchPoint {
                track_id: buf[0],
                x: u16::from_le_bytes([buf[1], buf[2]]),
                y: u16::from_le_bytes([buf[3], buf[4]]),
                size: u16::from_le_bytes([buf[5], buf[6]]),
            };

            debug!(
                "Touch point {}: x={}, y={}, size={}",
                i, points[i].x, points[i].y, points[i].size
            );
        }

        // Clear the buffer ready flag
        self.write_register(reg::POINT_INFO, &[0])?;

        Ok((num_points, points))
    }

    /// Read a single touch event (simplified interface)
    ///
    /// Returns a touch event if one is available, or None if no touch.
    pub fn read_touch(&mut self) -> Result<Option<TouchEvent>, DisplayError> {
        let (num_points, points) = self.read_touch_points()?;

        if num_points > 0 {
            let point = points[0];

            // Scale coordinates if resolution differs from display
            let x = if self.x_resolution == DISPLAY_WIDTH as u16 {
                point.x
            } else {
                ((point.x as u32) * DISPLAY_WIDTH / self.x_resolution as u32) as u16
            };

            let y = if self.y_resolution == DISPLAY_HEIGHT as u16 {
                point.y
            } else {
                ((point.y as u32) * DISPLAY_HEIGHT / self.y_resolution as u32) as u16
            };

            // Determine event type based on previous state
            let event = if self.last_touch.is_some() {
                TouchEvent::Move { x, y }
            } else {
                TouchEvent::Press { x, y }
            };

            self.last_touch = Some(TouchPoint { x, y, ..point });
            Ok(Some(event))
        } else if self.last_touch.is_some() {
            // Touch released
            let last = self.last_touch.take().unwrap();
            Ok(Some(TouchEvent::Release {
                x: last.x,
                y: last.y,
            }))
        } else {
            Ok(None)
        }
    }

    /// Soft reset the controller
    pub fn soft_reset(&mut self) -> Result<(), DisplayError> {
        self.write_register(reg::COMMAND, &[cmd::SOFT_RESET])
    }

    /// Read from a register
    fn read_register(&mut self, reg: u16, buf: &mut [u8]) -> Result<(), DisplayError> {
        let reg_bytes = reg.to_be_bytes();
        self.i2c
            .write_read(self.addr, &reg_bytes, buf)
            .map_err(|_| DisplayError::I2cError)
    }

    /// Write to a register
    fn write_register(&mut self, reg: u16, data: &[u8]) -> Result<(), DisplayError> {
        let reg_bytes = reg.to_be_bytes();
        let mut buf = [0u8; 10]; // Max write size
        buf[0] = reg_bytes[0];
        buf[1] = reg_bytes[1];
        let len = data.len().min(8);
        buf[2..2 + len].copy_from_slice(&data[..len]);

        self.i2c
            .write(self.addr, &buf[..2 + len])
            .map_err(|_| DisplayError::I2cError)
    }

    /// Release the I2C bus
    pub fn release(self) -> I2C {
        self.i2c
    }
}

/// GPIO pin assignments for touch controller
pub mod pins {
    /// I2C SDA pin
    pub const SDA: u8 = 4;
    /// I2C SCL pin
    pub const SCL: u8 = 5;
    /// Interrupt pin (active low)
    pub const INT: u8 = 1;
    /// Reset pin (active low)
    pub const RST: u8 = 38;
}

/// Initialize the GT911 with proper reset sequence
///
/// The I2C address is determined by the INT pin state during reset:
/// - INT HIGH during reset -> address 0x5D
/// - INT LOW during reset -> address 0x14
///
/// This function performs:
/// 1. Set INT as output, drive LOW
/// 2. Pulse RST LOW for 10ms
/// 3. Set INT HIGH (for 0x5D address) or keep LOW (for 0x14)
/// 4. Release RST
/// 5. Wait 50ms for initialization
/// 6. Set INT as input (floating with internal pull-up)
pub async fn init_gt911_reset() -> Result<(), DisplayError> {
    info!("Performing GT911 reset sequence");

    // TODO: Implement GPIO control for reset sequence
    // This requires access to GPIO pins from esp-hal

    // For now, assume the touch controller is already initialized by bootloader

    Ok(())
}
