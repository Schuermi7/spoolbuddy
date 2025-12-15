//! HX711 24-bit ADC driver.
//!
//! The HX711 is designed for weigh scales and industrial control applications
//! to interface directly with a bridge sensor.
//!
//! Pin connections:
//! - DOUT (DT) - Digital output (data), connect to GPIO input
//! - PD_SCK (SCK) - Power down / Serial clock, connect to GPIO output
//! - VCC - 2.7V to 5.5V
//! - GND - Ground
//!
//! Gain selection (by number of pulses after 24 data bits):
//! - 25 pulses: Channel A, gain 128 (default)
//! - 26 pulses: Channel B, gain 32
//! - 27 pulses: Channel A, gain 64
//!
//! Timing:
//! - SCK high time: min 0.2µs, typ 1µs
//! - SCK low time: min 0.2µs, typ 1µs
//! - SCK high >60µs puts chip in power down mode

use embedded_hal::digital::{InputPin, OutputPin};
use embassy_time::{Duration, Instant, Timer};

/// HX711 gain/channel selection
#[derive(Debug, Clone, Copy, Default)]
pub enum Gain {
    /// Channel A, gain 128 (25 pulses)
    #[default]
    ChannelA128 = 25,
    /// Channel B, gain 32 (26 pulses)
    ChannelB32 = 26,
    /// Channel A, gain 64 (27 pulses)
    ChannelA64 = 27,
}

/// HX711 driver
pub struct Hx711<DOUT, SCK> {
    dout: DOUT,
    sck: SCK,
    gain: Gain,
}

impl<DOUT, SCK> Hx711<DOUT, SCK>
where
    DOUT: InputPin,
    SCK: OutputPin,
{
    /// Create a new HX711 driver.
    pub fn new(dout: DOUT, sck: SCK) -> Self {
        Self {
            dout,
            sck,
            gain: Gain::default(),
        }
    }

    /// Brief delay (~1µs) using a busy-wait loop.
    /// At 240MHz, ~240 cycles ≈ 1µs
    #[inline(always)]
    fn delay_us() {
        // Volatile read to prevent optimization
        for _ in 0..50 {
            core::hint::spin_loop();
        }
    }

    /// Set the gain/channel for next reading.
    pub fn set_gain(&mut self, gain: Gain) {
        self.gain = gain;
    }

    /// Check if data is ready (DOUT low).
    pub fn is_ready(&mut self) -> bool {
        self.dout.is_low().unwrap_or(false)
    }

    /// Wait for data to be ready with timeout.
    pub async fn wait_ready(&mut self, timeout_ms: u32) -> Result<(), Hx711Error> {
        let start = Instant::now();
        let timeout = Duration::from_millis(timeout_ms as u64);

        while !self.is_ready() {
            if start.elapsed() > timeout {
                return Err(Hx711Error::Timeout);
            }
            Timer::after(Duration::from_micros(100)).await;
        }

        Ok(())
    }

    /// Read a single raw value from the HX711.
    ///
    /// Returns a 24-bit signed value (in i32).
    pub async fn read(&mut self) -> Result<i32, Hx711Error> {
        // Wait for data ready
        self.wait_ready(1000).await?;

        let mut value: u32 = 0;

        // Read 24 bits
        for _ in 0..24 {
            // Clock pulse
            let _ = self.sck.set_high();
            // Brief delay (~1µs) - busy wait loop
            Self::delay_us();

            // Read bit
            if self.dout.is_high().unwrap_or(false) {
                value = (value << 1) | 1;
            } else {
                value <<= 1;
            }

            let _ = self.sck.set_low();
            Self::delay_us();
        }

        // Send additional pulses to set gain for next reading
        let extra_pulses = self.gain as u8 - 24;
        for _ in 0..extra_pulses {
            let _ = self.sck.set_high();
            Self::delay_us();
            let _ = self.sck.set_low();
            Self::delay_us();
        }

        // Convert to signed 24-bit value
        // If bit 23 is set, the value is negative (2's complement)
        let signed_value = if value & 0x800000 != 0 {
            // Negative value - extend sign bit
            (value | 0xFF000000) as i32
        } else {
            value as i32
        };

        Ok(signed_value)
    }

    /// Read averaged value (multiple samples).
    pub async fn read_average(&mut self, samples: usize) -> Result<i32, Hx711Error> {
        if samples == 0 {
            return Err(Hx711Error::InvalidParameter);
        }

        let mut sum: i64 = 0;
        for _ in 0..samples {
            sum += self.read().await? as i64;
        }

        Ok((sum / samples as i64) as i32)
    }

    /// Power down the HX711.
    ///
    /// Set SCK high for >60µs to enter power down mode.
    pub fn power_down(&mut self) {
        let _ = self.sck.set_high();
    }

    /// Power up the HX711.
    ///
    /// Set SCK low to wake up from power down mode.
    pub fn power_up(&mut self) {
        let _ = self.sck.set_low();
    }
}

/// HX711 errors
#[derive(Debug, Clone, Copy)]
pub enum Hx711Error {
    Timeout,
    InvalidParameter,
}
