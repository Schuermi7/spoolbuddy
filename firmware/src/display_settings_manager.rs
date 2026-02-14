//! Display Settings Manager
//!
//! Persists display brightness and timeout to NVS flash
//! so they survive reboots.

use esp_idf_svc::nvs::{EspDefaultNvsPartition, EspNvs};
use log::{info, warn};
use std::sync::Mutex;

const NVS_NAMESPACE: &str = "display";
const NVS_KEY_SETTINGS: &str = "settings";

const DEFAULT_BRIGHTNESS: u8 = 80;
const DEFAULT_TIMEOUT: u16 = 300;

static NVS_PARTITION: Mutex<Option<EspDefaultNvsPartition>> = Mutex::new(None);

pub fn init_nvs(nvs: Option<EspDefaultNvsPartition>) {
    let mut guard = NVS_PARTITION.lock().unwrap();
    *guard = nvs;
    info!("Display NVS initialized");
}

pub fn load_settings() -> (u8, u16) {
    let nvs_guard = NVS_PARTITION.lock().unwrap();
    let Some(nvs_partition) = nvs_guard.as_ref() else {
        return (DEFAULT_BRIGHTNESS, DEFAULT_TIMEOUT);
    };

    let nvs = match EspNvs::new(nvs_partition.clone(), NVS_NAMESPACE, true) {
        Ok(nvs) => nvs,
        Err(e) => {
            warn!("Failed to open NVS namespace for display: {:?}", e);
            return (DEFAULT_BRIGHTNESS, DEFAULT_TIMEOUT);
        }
    };

    let mut buf = [0u8; 3];
    match nvs.get_blob(NVS_KEY_SETTINGS, &mut buf) {
        Ok(Some(_)) => {
            let brightness = buf[0];
            let timeout = u16::from_le_bytes([buf[1], buf[2]]);
            info!("Loaded display settings: brightness={}%, timeout={}s", brightness, timeout);
            (brightness, timeout)
        }
        Ok(None) => {
            info!("No saved display settings, using defaults");
            (DEFAULT_BRIGHTNESS, DEFAULT_TIMEOUT)
        }
        Err(e) => {
            warn!("Failed to read display settings from NVS: {:?}", e);
            (DEFAULT_BRIGHTNESS, DEFAULT_TIMEOUT)
        }
    }
}

pub fn save_settings(brightness: u8, timeout: u16) -> bool {
    let nvs_guard = NVS_PARTITION.lock().unwrap();
    let Some(nvs_partition) = nvs_guard.as_ref() else {
        warn!("No NVS partition available for saving display settings");
        return false;
    };

    let nvs = match EspNvs::new(nvs_partition.clone(), NVS_NAMESPACE, true) {
        Ok(nvs) => nvs,
        Err(e) => {
            warn!("Failed to open NVS namespace for display: {:?}", e);
            return false;
        }
    };

    let timeout_bytes = timeout.to_le_bytes();
    let buf = [brightness, timeout_bytes[0], timeout_bytes[1]];

    if let Err(e) = nvs.set_blob(NVS_KEY_SETTINGS, &buf) {
        warn!("Failed to save display settings to NVS: {:?}", e);
        return false;
    }

    info!("Display settings saved: brightness={}%, timeout={}s", brightness, timeout);
    true
}
