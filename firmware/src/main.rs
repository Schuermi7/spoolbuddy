//! SpoolBuddy Firmware for ESP32-S3-Touch-LCD-4.3
//!
//! This firmware handles:
//! - NFC tag reading (PN5180 via SPI)
//! - Scale weight reading (HX711 via GPIO)
//! - WiFi connection to SpoolBuddy server
//! - WebSocket communication for tag/weight data
//! - Display UI (800x480 touch screen)

#![no_std]
#![no_main]

use esp_backtrace as _;
use esp_hal::main;
use esp_println::println;
use log::info;

// ESP-IDF app descriptor required for flashing
esp_bootloader_esp_idf::esp_app_desc!();

// =============================================================================
// Hardcoded Configuration (for testing)
// =============================================================================

// TODO: Move to NVS storage with config portal
const WIFI_SSID: &str = "NYHC!"; // Set your WiFi SSID here for testing
#[allow(dead_code)]
const WIFI_PASSWORD: &str = "335288888"; // Set your WiFi password here for testing
const SERVER_URL: &str = "ws://spoolbuddy.local:8000/ws/device";

// =============================================================================
// Main Entry Point
// =============================================================================

#[main]
fn main() -> ! {
    // Small delay to let serial stabilize
    for _ in 0..1_000_000 {
        core::hint::spin_loop();
    }

    // Initialize logging
    esp_println::logger::init_logger_from_env();

    // Print startup banner
    for _ in 0..5 {
        println!("");
    }
    println!("====================================");
    println!("  SpoolBuddy Firmware v0.1.0");
    println!("====================================");
    info!("Initializing...");

    info!("Hardware initialized");

    // Check WiFi configuration
    if WIFI_SSID.is_empty() {
        info!("WiFi not configured - set WIFI_SSID and WIFI_PASSWORD in main.rs");
        info!("Running in offline mode...");
    } else {
        info!("WiFi configured for: {}", WIFI_SSID);
        info!("Server URL: {}", SERVER_URL);
    }

    // TODO: Initialize SPI for PN5180 NFC reader
    // TODO: Initialize GPIO for HX711 scale
    // TODO: Initialize display
    // TODO: Initialize WiFi
    // TODO: Start WebSocket client

    println!("");
    println!("SpoolBuddy is running!");
    println!("Waiting for NFC tag or scale reading...");
    println!("");

    let mut counter = 0u32;
    let mut last_heartbeat = 0u32;

    loop {
        counter = counter.wrapping_add(1);

        // Log heartbeat approximately every 5 seconds (rough timing)
        if counter.wrapping_sub(last_heartbeat) > 50_000_000 {
            last_heartbeat = counter;
            info!("Heartbeat - system running");
        }

        // TODO: Read scale value
        // TODO: Check for NFC tag
        // TODO: Update display
        // TODO: Send data to server
    }
}
