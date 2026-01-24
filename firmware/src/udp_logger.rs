//! UDP Logger - sends log messages to backend over UDP
//!
//! This allows logging even when UART pins are used for SPI.

use std::net::UdpSocket;
use std::sync::Mutex;
use std::sync::atomic::{AtomicBool, Ordering};

/// UDP logger state
static UDP_SOCKET: Mutex<Option<UdpSocket>> = Mutex::new(None);
static UDP_TARGET: Mutex<Option<String>> = Mutex::new(None);
static UDP_ENABLED: AtomicBool = AtomicBool::new(false);

/// Initialize UDP logger with target address (e.g., "192.168.1.100:5555")
pub fn init(target: &str) -> Result<(), std::io::Error> {
    let socket = UdpSocket::bind("0.0.0.0:0")?;
    socket.set_nonblocking(true)?;

    *UDP_SOCKET.lock().unwrap() = Some(socket);
    *UDP_TARGET.lock().unwrap() = Some(target.to_string());
    UDP_ENABLED.store(true, Ordering::SeqCst);

    // Send init message
    log("UDP logger initialized");
    Ok(())
}

/// Send a log message over UDP
pub fn log(msg: &str) {
    if !UDP_ENABLED.load(Ordering::Relaxed) {
        return;
    }

    let socket_guard = UDP_SOCKET.lock().unwrap();
    let target_guard = UDP_TARGET.lock().unwrap();

    if let (Some(socket), Some(target)) = (socket_guard.as_ref(), target_guard.as_ref()) {
        // Ignore send errors (non-blocking, best-effort)
        let _ = socket.send_to(msg.as_bytes(), target);
    }
}

/// Log with format (like println!)
#[macro_export]
macro_rules! udp_log {
    ($($arg:tt)*) => {
        $crate::udp_logger::log(&format!($($arg)*))
    };
}

/// Log info level
#[macro_export]
macro_rules! udp_info {
    ($($arg:tt)*) => {
        $crate::udp_logger::log(&format!("[INFO] {}", format!($($arg)*)))
    };
}

/// Log warning level
#[macro_export]
macro_rules! udp_warn {
    ($($arg:tt)*) => {
        $crate::udp_logger::log(&format!("[WARN] {}", format!($($arg)*)))
    };
}

/// Log error level
#[macro_export]
macro_rules! udp_error {
    ($($arg:tt)*) => {
        $crate::udp_logger::log(&format!("[ERROR] {}", format!($($arg)*)))
    };
}
