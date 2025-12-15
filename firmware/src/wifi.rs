//! WiFi connection management for SpoolBuddy device.
//!
//! Handles:
//! - WiFi station mode connection
//! - Reconnection on disconnect
//! - Configuration storage (NVS in production)

use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::signal::Signal;
use embassy_time::{Duration, Timer};
use heapless::String;
use log::{error, info, warn};

/// WiFi credentials - will be stored in NVS in production
#[derive(Clone)]
pub struct WifiConfig {
    pub ssid: String<32>,
    pub password: String<64>,
    pub server_url: String<128>,
}

impl WifiConfig {
    /// Create a new WiFi config with credentials.
    pub fn new(ssid: &str, password: &str, server_url: &str) -> Self {
        let mut config = Self {
            ssid: String::new(),
            password: String::new(),
            server_url: String::new(),
        };
        let _ = config.ssid.push_str(ssid);
        let _ = config.password.push_str(password);
        let _ = config.server_url.push_str(server_url);
        config
    }
}

impl Default for WifiConfig {
    fn default() -> Self {
        Self {
            ssid: String::new(),
            password: String::new(),
            server_url: String::new(),
        }
    }
}

/// WiFi connection state
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum WifiState {
    Disconnected,
    Connecting,
    Connected,
    Error,
}

/// WiFi connection status with IP info
#[derive(Debug, Clone)]
pub struct WifiStatus {
    pub state: WifiState,
    pub ip_address: Option<[u8; 4]>,
    pub ssid: String<32>,
}

impl Default for WifiStatus {
    fn default() -> Self {
        Self {
            state: WifiState::Disconnected,
            ip_address: None,
            ssid: String::new(),
        }
    }
}

/// Global WiFi status signal for sharing between tasks
pub static WIFI_STATUS: Signal<CriticalSectionRawMutex, WifiStatus> = Signal::new();

/// WiFi manager handles connection lifecycle
pub struct WifiManager {
    config: WifiConfig,
    status: WifiStatus,
}

impl WifiManager {
    /// Create a new WiFi manager with configuration.
    pub fn new(config: WifiConfig) -> Self {
        let mut status = WifiStatus::default();
        status.ssid = config.ssid.clone();

        Self { config, status }
    }

    /// Get current WiFi status.
    pub fn status(&self) -> &WifiStatus {
        &self.status
    }

    /// Check if connected.
    pub fn is_connected(&self) -> bool {
        self.status.state == WifiState::Connected
    }

    /// Update status and broadcast to listeners.
    fn update_status(&mut self, state: WifiState, ip: Option<[u8; 4]>) {
        self.status.state = state;
        self.status.ip_address = ip;
        WIFI_STATUS.signal(self.status.clone());
    }

    /// Connect to WiFi network.
    ///
    /// This is a placeholder - actual implementation requires esp-wifi integration
    /// in main.rs where peripherals are available.
    pub async fn connect(&mut self) -> Result<(), WifiError> {
        if self.config.ssid.is_empty() {
            error!("WiFi SSID not configured");
            self.update_status(WifiState::Error, None);
            return Err(WifiError::NotConfigured);
        }

        info!("Connecting to WiFi: {}", self.config.ssid.as_str());
        self.update_status(WifiState::Connecting, None);

        // TODO: Actual WiFi connection using esp-wifi
        // This requires the WiFi controller from main.rs
        // For now, this is a simulation for testing

        // Simulate connection delay
        Timer::after(Duration::from_secs(2)).await;

        // TODO: Replace with actual connection logic
        info!("WiFi connection stub - actual implementation needed");

        Ok(())
    }

    /// Disconnect from WiFi.
    pub async fn disconnect(&mut self) {
        info!("Disconnecting WiFi");
        self.update_status(WifiState::Disconnected, None);
    }
}

/// WiFi errors
#[derive(Debug, Clone, Copy)]
pub enum WifiError {
    NotConfigured,
    ConnectionFailed,
    AuthenticationFailed,
    Timeout,
    InternalError,
}

/// Format IP address as string.
pub fn format_ip(ip: [u8; 4]) -> String<16> {
    let mut s = String::new();
    use core::fmt::Write;
    let _ = write!(s, "{}.{}.{}.{}", ip[0], ip[1], ip[2], ip[3]);
    s
}

// =============================================================================
// ESP-WiFi Integration (called from main.rs)
// =============================================================================

/// Initialize WiFi hardware.
///
/// This should be called from main.rs where peripherals are available.
/// Returns the resources needed for WiFi operation.
///
/// Example usage in main.rs:
/// ```ignore
/// let wifi_init = esp_wifi::init(
///     EspWifiInitFor::Wifi,
///     timg1.timer0,
///     esp_hal::rng::Rng::new(peripherals.RNG),
///     peripherals.RADIO_CLK,
///     &clocks,
/// ).unwrap();
///
/// let (wifi_interface, controller) = esp_wifi::wifi::new_with_mode(
///     &wifi_init,
///     peripherals.WIFI,
///     WifiStaDevice,
/// ).unwrap();
/// ```
pub fn wifi_init_help() {
    info!("WiFi initialization helper - see wifi.rs for setup code");
}

// =============================================================================
// Configuration Portal (Future)
// =============================================================================

/// Start configuration portal (AP mode) for initial setup.
///
/// When WiFi credentials are not configured, the device starts an AP
/// named "SpoolBuddy-XXXX" with a captive portal for configuration.
pub async fn start_config_portal() {
    info!("Starting WiFi config portal (not yet implemented)");

    // TODO: Implement AP mode for configuration
    // 1. Start AP with name "SpoolBuddy-XXXX" (last 4 of MAC)
    // 2. Start DNS server redirecting all queries to self
    // 3. Start HTTP server with configuration page
    // 4. Accept WiFi credentials and server URL
    // 5. Store in NVS
    // 6. Restart in station mode
}
