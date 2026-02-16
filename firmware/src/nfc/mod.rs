
#[allow(dead_code)]

/// I2C bridge to Pico for NFC (recommended - more reliable than direct SPI)
pub mod i2c_bridge;

// I2C bridge re-exports (used by main.rs for I2C scan)
#[allow(unused_imports)]
pub use i2c_bridge::{NfcBridgeState, PICO_NFC_ADDR};
