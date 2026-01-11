//! NFC I2C Bridge Driver
//!
//! Communicates with the Pico NFC bridge over I2C.
//! The Pico handles PN5180 SPI communication and exposes a simple I2C interface.
//!
//! I2C Protocol:
//! - Address: 0x55
//! - Commands:
//!   - 0x00: Get status (returns 2 bytes: status, tag_present)
//!   - 0x01: Get version (returns 3 bytes: status, major, minor)
//!   - 0x10: Scan tag (returns: status, uid_len, uid[0..uid_len])

use esp_idf_hal::i2c::I2cDriver;
use log::{info, warn, debug};

/// I2C address of the Pico NFC bridge
pub const PICO_NFC_ADDR: u8 = 0x55;

/// Commands
#[allow(dead_code)]
const CMD_GET_STATUS: u8 = 0x00;
const CMD_GET_VERSION: u8 = 0x01;
const CMD_SCAN_TAG: u8 = 0x10;

/// NFC Bridge state
#[derive(Debug, Clone)]
pub struct NfcBridgeState {
    pub initialized: bool,
    pub firmware_version: (u8, u8),  // major, minor
    pub tag_present: bool,
    pub tag_uid: [u8; 10],
    pub tag_uid_len: u8,
}

impl NfcBridgeState {
    pub fn new() -> Self {
        Self {
            initialized: false,
            firmware_version: (0, 0),
            tag_present: false,
            tag_uid: [0; 10],
            tag_uid_len: 0,
        }
    }
}

/// Initialize the NFC I2C bridge
pub fn init_bridge(i2c: &mut I2cDriver<'_>, state: &mut NfcBridgeState) -> Result<(), &'static str> {
    info!("=== NFC I2C BRIDGE INIT ===");
    info!("  Pico address: 0x{:02X}", PICO_NFC_ADDR);

    // Check if Pico is present
    let mut buf = [0u8; 1];
    if i2c.read(PICO_NFC_ADDR, &mut buf, 100).is_err() {
        warn!("  Pico NFC bridge not found at 0x{:02X}", PICO_NFC_ADDR);
        return Err("Pico not found");
    }
    info!("  Pico NFC bridge detected");

    // Get version
    match get_version(i2c) {
        Ok((major, minor)) => {
            info!("  Pico firmware: {}.{}", major, minor);
            state.firmware_version = (major, minor);
        }
        Err(e) => {
            warn!("  Failed to get version: {}", e);
        }
    }

    state.initialized = true;
    info!("=== NFC I2C BRIDGE READY ===");
    Ok(())
}

/// Get Pico firmware version
pub fn get_version(i2c: &mut I2cDriver<'_>) -> Result<(u8, u8), &'static str> {
    // Send command
    let cmd = [CMD_GET_VERSION];
    if i2c.write(PICO_NFC_ADDR, &cmd, 100).is_err() {
        return Err("I2C write failed");
    }

    // Small delay for Pico to process
    std::thread::sleep(std::time::Duration::from_millis(10));

    // Read response: [status, major, minor]
    let mut resp = [0u8; 3];
    if i2c.read(PICO_NFC_ADDR, &mut resp, 100).is_err() {
        return Err("I2C read failed");
    }

    if resp[0] != 0 {
        return Err("Command failed");
    }

    Ok((resp[1], resp[2]))
}

/// Scan for a tag
pub fn scan_tag(i2c: &mut I2cDriver<'_>, state: &mut NfcBridgeState) -> Result<bool, &'static str> {
    // Send scan command
    let cmd = [CMD_SCAN_TAG];
    if i2c.write(PICO_NFC_ADDR, &cmd, 100).is_err() {
        return Err("I2C write failed");
    }

    // Wait for scan to complete (Pico needs time to do RF communication)
    // Hard reset can take 300-500ms, so wait longer
    std::thread::sleep(std::time::Duration::from_millis(500));

    // Read response: [status, uid_len, uid...]
    let mut resp = [0u8; 12];  // Max: status + len + 10 UID bytes
    if i2c.read(PICO_NFC_ADDR, &mut resp, 100).is_err() {
        return Err("I2C read failed");
    }

    if resp[0] != 0 {
        // No tag or error
        state.tag_present = false;
        state.tag_uid_len = 0;
        return Ok(false);
    }

    let uid_len = resp[1];
    if uid_len > 0 && uid_len <= 10 {
        state.tag_present = true;
        state.tag_uid_len = uid_len;
        state.tag_uid[..uid_len as usize].copy_from_slice(&resp[2..2 + uid_len as usize]);

        debug!("Tag found: {:02X?}", &state.tag_uid[..uid_len as usize]);
        Ok(true)
    } else {
        state.tag_present = false;
        state.tag_uid_len = 0;
        Ok(false)
    }
}

/// Get UID as hex string
#[allow(dead_code)]
pub fn get_uid_hex(state: &NfcBridgeState) -> Option<String> {
    if !state.tag_present || state.tag_uid_len == 0 {
        return None;
    }

    let hex: String = state.tag_uid[..state.tag_uid_len as usize]
        .iter()
        .map(|b| format!("{:02X}", b))
        .collect::<Vec<_>>()
        .join(":");

    Some(hex)
}
