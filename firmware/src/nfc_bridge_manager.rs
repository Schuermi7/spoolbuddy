//! NFC Bridge Manager with C-callable interface
//!
//! Provides FFI functions for the C UI code to access NFC tag data.
//! Uses the Pico NFC bridge over I2C.

use log::{info, warn};
use std::sync::Mutex;

use crate::nfc::i2c_bridge::{self, NfcBridgeState};
use crate::shared_i2c;

/// Global NFC state protected by mutex
static NFC_STATE: Mutex<Option<NfcBridgeState>> = Mutex::new(None);

/// NFC status for C code
#[repr(C)]
pub struct NfcStatus {
    pub initialized: bool,
    pub tag_present: bool,
    pub uid_len: u8,
    pub uid: [u8; 10],
}

/// Initialize the NFC bridge manager
pub fn init_nfc_manager() -> bool {
    // Use shared I2C to initialize
    let result = shared_i2c::with_i2c(|i2c| {
        let mut state = NfcBridgeState::new();
        match i2c_bridge::init_bridge(i2c, &mut state) {
            Ok(()) => {
                info!("NFC bridge manager initialized");
                Some(state)
            }
            Err(e) => {
                warn!("NFC bridge init failed: {}", e);
                None
            }
        }
    });

    if let Some(Some(state)) = result {
        let mut guard = NFC_STATE.lock().unwrap();
        *guard = Some(state);
        true
    } else {
        false
    }
}

/// Poll the NFC bridge (call from main loop)
pub fn poll_nfc() {
    let mut guard = NFC_STATE.lock().unwrap();
    if let Some(ref mut state) = *guard {
        if state.initialized {
            // Use shared I2C to scan
            static mut LAST_TAG_PRESENT: bool = false;
            let _ = shared_i2c::with_i2c(|i2c| {
                match i2c_bridge::scan_tag(i2c, state) {
                    Ok(found) => {
                        unsafe {
                            if found && !LAST_TAG_PRESENT {
                                // Tag just appeared
                                info!("NFC TAG DETECTED: {:02X?}", &state.tag_uid[..state.tag_uid_len as usize]);
                            } else if !found && LAST_TAG_PRESENT {
                                // Tag just removed
                                info!("NFC TAG REMOVED");
                            }
                            LAST_TAG_PRESENT = found;
                        }
                    }
                    Err(e) => {
                        warn!("NFC scan error: {}", e);
                    }
                }
            });
        }
    }
}

// =============================================================================
// C-callable FFI functions
// =============================================================================

/// Get current NFC status
#[no_mangle]
pub extern "C" fn nfc_get_status(status: *mut NfcStatus) {
    if status.is_null() {
        return;
    }

    let guard = NFC_STATE.lock().unwrap();
    let status = unsafe { &mut *status };

    if let Some(ref state) = *guard {
        status.initialized = state.initialized;
        status.tag_present = state.tag_present;
        status.uid_len = state.tag_uid_len;
        status.uid = state.tag_uid;
    } else {
        status.initialized = false;
        status.tag_present = false;
        status.uid_len = 0;
        status.uid = [0; 10];
    }
}

/// Check if NFC is initialized
#[no_mangle]
pub extern "C" fn nfc_is_initialized() -> bool {
    let guard = NFC_STATE.lock().unwrap();
    if let Some(ref state) = *guard {
        state.initialized
    } else {
        false
    }
}

/// Check if a tag is present
#[no_mangle]
pub extern "C" fn nfc_tag_present() -> bool {
    let guard = NFC_STATE.lock().unwrap();
    if let Some(ref state) = *guard {
        state.tag_present
    } else {
        false
    }
}

/// Get tag UID length (0 if no tag)
#[no_mangle]
pub extern "C" fn nfc_get_uid_len() -> u8 {
    let guard = NFC_STATE.lock().unwrap();
    if let Some(ref state) = *guard {
        if state.tag_present {
            state.tag_uid_len
        } else {
            0
        }
    } else {
        0
    }
}

/// Copy tag UID to buffer (returns actual length copied)
#[no_mangle]
pub extern "C" fn nfc_get_uid(buf: *mut u8, buf_len: u8) -> u8 {
    if buf.is_null() || buf_len == 0 {
        return 0;
    }

    let guard = NFC_STATE.lock().unwrap();
    if let Some(ref state) = *guard {
        if state.tag_present && state.tag_uid_len > 0 {
            let copy_len = std::cmp::min(state.tag_uid_len, buf_len) as usize;
            unsafe {
                std::ptr::copy_nonoverlapping(state.tag_uid.as_ptr(), buf, copy_len);
            }
            return copy_len as u8;
        }
    }
    0
}

/// Get UID as hex string (for display)
/// Writes to buf, returns length written (not including null terminator)
#[no_mangle]
pub extern "C" fn nfc_get_uid_hex(buf: *mut u8, buf_len: u8) -> u8 {
    if buf.is_null() || buf_len < 3 {
        return 0;
    }

    let guard = NFC_STATE.lock().unwrap();
    if let Some(ref state) = *guard {
        if state.tag_present && state.tag_uid_len > 0 {
            // Format: "XX:XX:XX:XX" - each byte is 2 chars + separator
            let max_bytes = ((buf_len as usize) + 1) / 3;  // Account for : separators
            let uid_len = std::cmp::min(state.tag_uid_len as usize, max_bytes);

            let mut pos = 0usize;
            for i in 0..uid_len {
                if pos + 2 > buf_len as usize {
                    break;
                }
                let hex_chars: [u8; 16] = *b"0123456789ABCDEF";
                let byte = state.tag_uid[i];
                unsafe {
                    *buf.add(pos) = hex_chars[(byte >> 4) as usize];
                    *buf.add(pos + 1) = hex_chars[(byte & 0x0F) as usize];
                }
                pos += 2;

                // Add separator if not last byte
                if i < uid_len - 1 && pos < buf_len as usize {
                    unsafe {
                        *buf.add(pos) = b':';
                    }
                    pos += 1;
                }
            }

            return pos as u8;
        }
    }
    0
}
