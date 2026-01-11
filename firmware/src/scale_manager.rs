//! Scale Manager with C-callable interface
//!
//! Provides FFI functions for the C UI code to access scale data.
//! Uses shared I2C bus.

use log::info;
use std::sync::Mutex;

use crate::scale::nau7802::{self, Nau7802State};
use crate::shared_i2c;

/// Global scale state protected by mutex
static SCALE_STATE: Mutex<Option<Nau7802State>> = Mutex::new(None);

/// Scale status for C code
#[repr(C)]
pub struct ScaleStatus {
    pub initialized: bool,
    pub weight_grams: f32,
    pub raw_value: i32,
    pub stable: bool,
    pub tare_offset: i32,
    pub cal_factor: f32,
}

/// Initialize the scale manager with state (uses shared I2C)
pub fn init_scale_manager(state: Nau7802State) {
    let mut guard = SCALE_STATE.lock().unwrap();
    *guard = Some(state);
    info!("Scale manager initialized");
}

/// Poll the scale (call from main loop)
pub fn poll_scale() {
    let mut guard = SCALE_STATE.lock().unwrap();
    if let Some(ref mut state) = *guard {
        if state.initialized {
            let _ = shared_i2c::with_i2c(|i2c| {
                nau7802::read_weight(i2c, state)
            });
        }
    }
}

// =============================================================================
// C-callable FFI functions
// =============================================================================

/// Get current scale status
#[no_mangle]
pub extern "C" fn scale_get_status(status: *mut ScaleStatus) {
    if status.is_null() {
        return;
    }

    let guard = SCALE_STATE.lock().unwrap();
    let status = unsafe { &mut *status };

    if let Some(ref state) = *guard {
        status.initialized = state.initialized;
        status.weight_grams = state.weight_grams;
        status.raw_value = state.last_raw;
        status.stable = state.stable;
        status.tare_offset = state.calibration.zero_offset;
        status.cal_factor = state.calibration.cal_factor;
    } else {
        status.initialized = false;
        status.weight_grams = 0.0;
        status.raw_value = 0;
        status.stable = false;
        status.tare_offset = 0;
        status.cal_factor = 1.0;
    }
}

/// Get current weight in grams
#[no_mangle]
pub extern "C" fn scale_get_weight() -> f32 {
    let guard = SCALE_STATE.lock().unwrap();
    if let Some(ref state) = *guard {
        state.weight_grams
    } else {
        0.0
    }
}

/// Get raw ADC value
#[no_mangle]
pub extern "C" fn scale_get_raw() -> i32 {
    let guard = SCALE_STATE.lock().unwrap();
    if let Some(ref state) = *guard {
        state.last_raw
    } else {
        0
    }
}

/// Check if scale is initialized
#[no_mangle]
pub extern "C" fn scale_is_initialized() -> bool {
    let guard = SCALE_STATE.lock().unwrap();
    if let Some(ref state) = *guard {
        state.initialized
    } else {
        false
    }
}

/// Check if weight is stable
#[no_mangle]
pub extern "C" fn scale_is_stable() -> bool {
    let guard = SCALE_STATE.lock().unwrap();
    if let Some(ref state) = *guard {
        state.stable
    } else {
        false
    }
}

/// Tare the scale (set current weight as zero)
#[no_mangle]
pub extern "C" fn scale_tare() -> i32 {
    let mut guard = SCALE_STATE.lock().unwrap();
    if let Some(ref mut state) = *guard {
        let result = shared_i2c::with_i2c(|i2c| {
            nau7802::tare(i2c, state)
        });
        match result {
            Some(Ok(())) => 0,
            _ => -1,
        }
    } else {
        -1
    }
}

/// Calibrate with a known weight (in grams)
#[no_mangle]
pub extern "C" fn scale_calibrate(known_weight_grams: f32) -> i32 {
    let mut guard = SCALE_STATE.lock().unwrap();
    if let Some(ref mut state) = *guard {
        let result = shared_i2c::with_i2c(|i2c| {
            nau7802::calibrate(i2c, state, known_weight_grams)
        });
        match result {
            Some(Ok(())) => 0,
            _ => -1,
        }
    } else {
        -1
    }
}

/// Get tare offset
#[no_mangle]
pub extern "C" fn scale_get_tare_offset() -> i32 {
    let guard = SCALE_STATE.lock().unwrap();
    if let Some(ref state) = *guard {
        state.calibration.zero_offset
    } else {
        0
    }
}
