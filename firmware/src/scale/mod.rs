//! Scale module for HX711 load cell amplifier.
//!
//! The HX711 is a precision 24-bit ADC designed for weigh scales.
//! Communication is via a simple 2-wire interface:
//! - DOUT (DT) - Data output
//! - PD_SCK (SCK) - Clock input
//!
//! Reading sequence:
//! 1. Wait for DOUT to go low (data ready)
//! 2. Clock out 24-25 bits (24 data + gain select)
//! 3. Process 2's complement value

pub mod hx711;

use embassy_time::{Duration, Timer};
use log::info;

/// Scale state
pub struct Scale {
    /// Calibration offset (tare value)
    offset: i32,
    /// Calibration scale factor (raw units per gram)
    scale: f32,
    /// Last stable weight in grams
    last_weight: f32,
    /// Is weight currently stable?
    stable: bool,
    /// Number of consecutive stable readings
    stable_count: u8,
}

impl Scale {
    pub fn new() -> Self {
        Self {
            offset: 0,
            scale: 1.0,
            last_weight: 0.0,
            stable: false,
            stable_count: 0,
        }
    }

    /// Initialize the scale with calibration values.
    pub fn init(&mut self, offset: i32, scale: f32) {
        self.offset = offset;
        self.scale = scale;
        info!("Scale initialized: offset={}, scale={}", offset, scale);
    }

    /// Read raw value from HX711 (stub).
    pub async fn read_raw(&mut self) -> Result<i32, ScaleError> {
        // TODO: Implement actual HX711 reading
        info!("Reading raw scale value (stub)");
        Ok(0)
    }

    /// Read weight in grams.
    pub async fn read_grams(&mut self) -> Result<f32, ScaleError> {
        let raw = self.read_raw().await?;
        let grams = (raw - self.offset) as f32 / self.scale;
        Ok(grams)
    }

    /// Read weight with stability detection.
    ///
    /// Returns (weight_grams, is_stable).
    pub async fn read_stable(&mut self) -> Result<(f32, bool), ScaleError> {
        let weight = self.read_grams().await?;

        // Check if weight is stable (within 0.5g of last reading)
        let diff = (weight - self.last_weight).abs();
        if diff < 0.5 {
            self.stable_count = self.stable_count.saturating_add(1);
            if self.stable_count >= 5 {
                self.stable = true;
            }
        } else {
            self.stable_count = 0;
            self.stable = false;
        }

        self.last_weight = weight;
        Ok((weight, self.stable))
    }

    /// Tare the scale (set current weight as zero).
    pub async fn tare(&mut self) -> Result<(), ScaleError> {
        // Average multiple readings for tare
        let mut sum: i64 = 0;
        const SAMPLES: usize = 10;

        for _ in 0..SAMPLES {
            sum += self.read_raw().await? as i64;
            Timer::after(Duration::from_millis(50)).await;
        }

        self.offset = (sum / SAMPLES as i64) as i32;
        info!("Scale tared: offset={}", self.offset);
        Ok(())
    }

    /// Calibrate the scale with a known weight.
    pub async fn calibrate(&mut self, known_weight_grams: f32) -> Result<(), ScaleError> {
        // Average multiple readings
        let mut sum: i64 = 0;
        const SAMPLES: usize = 10;

        for _ in 0..SAMPLES {
            sum += self.read_raw().await? as i64;
            Timer::after(Duration::from_millis(50)).await;
        }

        let avg_raw = (sum / SAMPLES as i64) as i32;
        self.scale = (avg_raw - self.offset) as f32 / known_weight_grams;

        info!(
            "Scale calibrated: scale={} (known weight: {}g)",
            self.scale, known_weight_grams
        );
        Ok(())
    }

    /// Get current calibration values.
    pub fn get_calibration(&self) -> (i32, f32) {
        (self.offset, self.scale)
    }
}

/// Scale errors
#[derive(Debug, Clone, Copy)]
pub enum ScaleError {
    NotReady,
    Timeout,
    InvalidReading,
}
