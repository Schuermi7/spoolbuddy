//! Shared I2C bus for multiple devices
//!
//! Holds the I2C driver in a static Mutex so multiple managers can share it.

use esp_idf_hal::i2c::I2cDriver;
use std::sync::Mutex;

/// Global shared I2C bus
static SHARED_I2C: Mutex<Option<I2cDriver<'static>>> = Mutex::new(None);

/// Initialize the shared I2C bus
pub fn init_shared_i2c(i2c: I2cDriver<'static>) {
    let mut guard = SHARED_I2C.lock().unwrap();
    *guard = Some(i2c);
}

/// Access the shared I2C bus with a closure
/// Returns None if I2C is not initialized
pub fn with_i2c<F, R>(f: F) -> Option<R>
where
    F: FnOnce(&mut I2cDriver<'static>) -> R,
{
    let mut guard = SHARED_I2C.lock().unwrap();
    guard.as_mut().map(f)
}

/// Check if I2C is initialized
#[allow(dead_code)]
pub fn is_initialized() -> bool {
    let guard = SHARED_I2C.lock().unwrap();
    guard.is_some()
}
