//! SpoolBuddy Firmware
//! ESP32-S3 with ELECROW CrowPanel 7.0" (800x480 RGB565)
//! Using LVGL 9.x with EEZ Studio generated UI

use esp_idf_hal::delay::FreeRtos;
// use esp_idf_hal::gpio::PinDriver;
use esp_idf_hal::i2c::{I2cConfig, I2cDriver};
use esp_idf_hal::peripherals::Peripherals;
use esp_idf_hal::units::Hertz;
use esp_idf_svc::eventloop::EspSystemEventLoop;
use esp_idf_svc::nvs::EspDefaultNvsPartition;
use esp_idf_sys as _;
use log::{info, warn};

// Scale module for NAU7802
mod scale;

// Scale manager with C-callable interface
mod scale_manager;

// NFC module for PN5180 and I2C bridge
mod nfc;

// Shared I2C bus for scale and NFC
mod shared_i2c;

// NFC bridge manager (Pico I2C bridge)
mod nfc_bridge_manager;

// WiFi manager with C-callable interface
mod wifi_manager;

// Backend client for server communication
mod backend_client;

// Time manager for NTP sync
mod time_manager;

// OTA update manager
mod ota_manager;

// Display driver C functions (handles LVGL init and EEZ UI)
extern "C" {
    fn display_init() -> i32;
    fn display_tick();
    fn display_set_backlight_hw(brightness_percent: u8);
}

// =============================================================================
// Display Settings FFI (called from C UI code)
// =============================================================================

static mut DISPLAY_BRIGHTNESS: u8 = 80;
static mut DISPLAY_TIMEOUT: u16 = 300;

#[no_mangle]
pub extern "C" fn display_set_brightness(brightness: u8) {
    let brightness = if brightness > 100 { 100 } else { brightness };
    unsafe {
        DISPLAY_BRIGHTNESS = brightness;
        // Actually set hardware backlight via I2C
        display_set_backlight_hw(brightness);
    }
    info!("Display brightness set to {}%", brightness);
    let timeout = unsafe { DISPLAY_TIMEOUT };
    display_settings_manager::save_settings(brightness, timeout);
}

#[no_mangle]
pub extern "C" fn display_get_brightness() -> u8 {
    unsafe { DISPLAY_BRIGHTNESS }
}

#[no_mangle]
pub extern "C" fn display_set_timeout(timeout_seconds: u16) {
    unsafe {
        DISPLAY_TIMEOUT = timeout_seconds;
    }
    info!("Display timeout set to {} seconds", timeout_seconds);
    let brightness = unsafe { DISPLAY_BRIGHTNESS };
    display_settings_manager::save_settings(brightness, timeout_seconds);
}

#[no_mangle]
pub extern "C" fn display_get_timeout() -> u16 {
    unsafe { DISPLAY_TIMEOUT }
}

fn main() {
    // Initialize ESP-IDF
    esp_idf_svc::sys::link_patches();
    esp_idf_svc::log::EspLogger::initialize_default();

    info!("SpoolBuddy Firmware starting...");

    let peripherals = Peripherals::take().unwrap();

    // Initialize WiFi subsystem (must be done before display init uses I2C0)
    let sysloop = EspSystemEventLoop::take().expect("Failed to take system event loop");
    let nvs = EspDefaultNvsPartition::take().ok();

    // Clone NVS partitions for persistence
    let nvs_for_scale = nvs.clone();
    let nvs_for_display = nvs.clone();

    match wifi_manager::init_wifi_system(peripherals.modem, sysloop, nvs) {
        Ok(_) => info!("WiFi subsystem ready"),
        Err(e) => warn!("WiFi init failed: {}", e),
    }

    // Initialize scale NVS (for calibration persistence)
    scale_manager::init_nvs(nvs_for_scale);

    // Initialize display settings NVS (for brightness/timeout persistence)
    display_settings_manager::init_nvs(nvs_for_display);

    // Initialize backend client (for server communication)
    backend_client::init();

    // Initialize display, LVGL, and EEZ UI via C driver
    // Display uses I2C0 (GPIO15/16) for touch controller
    unsafe {
        info!("Initializing display and UI...");
        let result = display_init();
        if result != 0 {
            info!("Display init failed with code: {}", result);
        }
    }

    // Load and apply saved display settings
    {
        let (brightness, timeout) = display_settings_manager::load_settings();
        unsafe {
            DISPLAY_BRIGHTNESS = brightness;
            DISPLAY_TIMEOUT = timeout;
            display_set_backlight_hw(brightness);
        }
        info!("Display settings applied: brightness={}%, timeout={}s", brightness, timeout);
    }

    // Initialize shared I2C bus on UART1-OUT port
    // UART1-OUT pinout: IO19-RX1, IO20-TX1, 3V3, GND
    // Using: GPIO19=SDA, GPIO20=SCL
    // This bus is shared between scale (NAU7802) and NFC bridge (Pico at 0x55)
    info!("=== SHARED I2C INIT (UART1-OUT: GPIO19/20) ===");
    let i2c1_config = I2cConfig::new().baudrate(Hertz(100_000));
    match I2cDriver::new(
        peripherals.i2c1,
        peripherals.pins.gpio19,  // SDA (UART1-OUT IO19-RX1)
        peripherals.pins.gpio20,  // SCL (UART1-OUT IO20-TX1)
        &i2c1_config,
    ) {
        Ok(i2c) => {
            info!("I2C1 initialized (SDA=GPIO19, SCL=GPIO20 on UART1-OUT)");

            // Leak the I2C driver to get 'static lifetime
            let i2c_static: &'static mut I2cDriver<'static> = Box::leak(Box::new(i2c));

            // Scan I2C1 for devices
            info!("Scanning I2C1 bus...");
            let mut found_nau7802 = false;
            let mut found_pico = false;
            for addr in 0x08..0x78 {
                let mut buf = [0u8; 1];
                if i2c_static.read(addr, &mut buf, 100).is_ok() {
                    info!("  Found I2C device at 0x{:02X}", addr);
                    if addr == scale::nau7802::NAU7802_ADDR {
                        info!("  -> NAU7802 scale chip detected!");
                        found_nau7802 = true;
                    }
                    if addr == nfc::i2c_bridge::PICO_NFC_ADDR {
                        info!("  -> Pico NFC bridge detected!");
                        found_pico = true;
                    }
                }
            }
            if !found_nau7802 {
                warn!("  NAU7802 not found at 0x{:02X}", scale::nau7802::NAU7802_ADDR);
            }
            if !found_pico {
                warn!("  Pico NFC bridge not found at 0x{:02X}", nfc::i2c_bridge::PICO_NFC_ADDR);
            }

            // Initialize scale if found
            if found_nau7802 {
                let mut scale_state = scale::nau7802::Nau7802State::new();
                match scale::nau7802::init(i2c_static, &mut scale_state) {
                    Ok(()) => {
                        info!("NAU7802 scale initialized");
                        scale_manager::init_scale_manager(scale_state);
                    }
                    Err(e) => warn!("NAU7802 init failed: {:?}", e),
                }
            }

            // Take ownership back and give to shared_i2c
            let i2c_owned = unsafe { Box::from_raw(i2c_static as *mut I2cDriver<'static>) };
            shared_i2c::init_shared_i2c(*i2c_owned);

            // Initialize NFC bridge manager (uses shared I2C)
            if found_pico {
                if nfc_bridge_manager::init_nfc_manager() {
                    info!("NFC bridge manager initialized");
                } else {
                    warn!("NFC bridge manager init failed");
                }
            }
        }
        Err(e) => {
            warn!("I2C1 init failed: {:?}", e);
        }
    }
    info!("=== SHARED I2C DONE ===");

    info!("Entering main loop...");

    // Main loop counter for periodic tasks
    let mut loop_count: u32 = 0;

    // Main loop
    loop {
        unsafe {
            display_tick();
        }

        // Poll scale every 10 iterations (~50ms at 5ms delay)
        loop_count = loop_count.wrapping_add(1);
        if loop_count % 10 == 0 {
            scale_manager::poll_scale();
        }

        // Post-WiFi initialization - check frequently until WiFi connects
        static WIFI_INIT_DONE: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
        static OTA_CHECK_DONE: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
        if !WIFI_INIT_DONE.load(std::sync::atomic::Ordering::Relaxed) {
            if loop_count % 20 == 0 && wifi_manager::is_connected() {
                // Initialize SNTP for time sync (may take time)
                time_manager::init_sntp();
                // Set backend server URL
                backend_client::set_server_url("http://192.168.178.71:3000");
                // Sync time immediately from backend (faster than SNTP)
                backend_client::sync_time();
                WIFI_INIT_DONE.store(true, std::sync::atomic::Ordering::Relaxed);
                info!("Post-WiFi init complete (SNTP + backend URL + time sync)");
                // Immediate first poll for printer data
                backend_client::poll_backend();
            }
        } else if loop_count % 400 == 0 {
            // Regular polling every 2 seconds (full sync: printers, commands, etc.)
            backend_client::poll_backend();
        } else if loop_count % 100 == 0 {
            // Weight-only update every 500ms for faster UI feedback
            let weight = scale_manager::scale_get_weight();
            let stable = scale_manager::scale_is_stable();
            backend_client::send_device_state(None, weight, stable);
        }

        // OTA check on startup (once, after WiFi init) - check but don't auto-install
        // Updates are triggered via backend command
        if WIFI_INIT_DONE.load(std::sync::atomic::Ordering::Relaxed)
            && !OTA_CHECK_DONE.load(std::sync::atomic::Ordering::Relaxed)
        {
            OTA_CHECK_DONE.store(true, std::sync::atomic::Ordering::Relaxed);
            info!("Firmware version: v{}", ota_manager::get_version());

            // Check for updates and store result (don't auto-install)
            match ota_manager::check_for_update("http://192.168.255.16:3000") {
                Ok(info) => {
                    if info.available {
                        info!("Firmware update available: v{}", info.version);
                        ota_manager::set_update_available(true, &info.version);
                    } else {
                        info!("Firmware is up to date");
                        ota_manager::set_update_available(false, "");
                    }
                }
                Err(e) => {
                    warn!("OTA check failed: {}", e);
                }
            }
        }

        // Poll NFC bridge every 100 iterations (~500ms at 5ms delay)
        if loop_count % 100 == 0 {
            nfc_bridge_manager::poll_nfc();
        }

        FreeRtos::delay_ms(5);
    }
}
