//! PN5180 NFC controller driver.
//!
//! The PN5180 communicates via SPI with the following pins:
//! - MOSI, MISO, SCLK - Standard SPI
//! - NSS - Chip select (directly controlled, active low)
//! - BUSY - Indicates when chip is processing (active high)
//! - RST - Hardware reset (active low)
//!
//! Commands are sent as:
//! [CMD_BYTE] [PAYLOAD...]
//!
//! Responses are read after BUSY goes low.

use embedded_hal::spi::SpiDevice;
use log::{debug, error, info};

/// PN5180 command codes
#[allow(dead_code)]
pub mod commands {
    pub const WRITE_REGISTER: u8 = 0x00;
    pub const WRITE_REGISTER_OR_MASK: u8 = 0x01;
    pub const WRITE_REGISTER_AND_MASK: u8 = 0x02;
    pub const READ_REGISTER: u8 = 0x04;
    pub const WRITE_EEPROM: u8 = 0x06;
    pub const READ_EEPROM: u8 = 0x07;
    pub const SEND_DATA: u8 = 0x09;
    pub const READ_DATA: u8 = 0x0A;
    pub const SWITCH_MODE: u8 = 0x0B;
    pub const MIFARE_AUTHENTICATE: u8 = 0x0C;
    pub const EPC_INVENTORY: u8 = 0x0D;
    pub const EPC_RESUME_INVENTORY: u8 = 0x0E;
    pub const EPC_RETRIEVE_INVENTORY_RESULT_SIZE: u8 = 0x0F;
    pub const EPC_RETRIEVE_INVENTORY_RESULT: u8 = 0x10;
    pub const LOAD_RF_CONFIG: u8 = 0x11;
    pub const UPDATE_RF_CONFIG: u8 = 0x12;
    pub const RETRIEVE_RF_CONFIG_SIZE: u8 = 0x13;
    pub const RETRIEVE_RF_CONFIG: u8 = 0x14;
    pub const RF_ON: u8 = 0x16;
    pub const RF_OFF: u8 = 0x17;
}

/// PN5180 register addresses
#[allow(dead_code)]
pub mod registers {
    pub const SYSTEM_CONFIG: u8 = 0x00;
    pub const IRQ_ENABLE: u8 = 0x01;
    pub const IRQ_STATUS: u8 = 0x02;
    pub const IRQ_CLEAR: u8 = 0x03;
    pub const TRANSCEIVE_CONTROL: u8 = 0x04;
    pub const TIMER1_CONFIG: u8 = 0x0F;
    pub const TIMER1_RELOAD: u8 = 0x10;
    pub const TIMER1_VALUE: u8 = 0x11;
    pub const TX_DATA_NUM: u8 = 0x14;
    pub const RX_STATUS: u8 = 0x15;
    pub const RF_STATUS: u8 = 0x1D;
}

/// RF configuration protocols
#[allow(dead_code)]
pub mod rf_config {
    pub const ISO_14443A_106_TX: u8 = 0x00;
    pub const ISO_14443A_106_RX: u8 = 0x80;
    pub const ISO_14443A_212_TX: u8 = 0x01;
    pub const ISO_14443A_212_RX: u8 = 0x81;
    pub const ISO_14443A_424_TX: u8 = 0x02;
    pub const ISO_14443A_424_RX: u8 = 0x82;
    pub const ISO_14443A_848_TX: u8 = 0x03;
    pub const ISO_14443A_848_RX: u8 = 0x83;
}

/// MIFARE authentication key type
#[derive(Debug, Clone, Copy)]
pub enum MifareKeyType {
    KeyA,
    KeyB,
}

/// Bambu Lab MIFARE key (Crypto-1)
/// Note: This is the known key for reading Bambu Lab tags
pub const BAMBULAB_KEY: [u8; 6] = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]; // Placeholder - actual key needed

/// PN5180 driver
pub struct Pn5180<SPI> {
    spi: SPI,
    // Note: BUSY and RST pins would be passed in separately
}

impl<SPI> Pn5180<SPI>
where
    SPI: SpiDevice,
{
    pub fn new(spi: SPI) -> Self {
        Self { spi }
    }

    /// Reset the PN5180.
    pub async fn reset(&mut self) -> Result<(), Pn5180Error> {
        // TODO: Toggle RST pin low then high
        // Wait for BUSY to go low
        info!("PN5180 reset (stub)");
        Ok(())
    }

    /// Read firmware version.
    pub async fn get_firmware_version(&mut self) -> Result<(u8, u8, u8), Pn5180Error> {
        // TODO: Read EEPROM address 0x10-0x12
        info!("Reading PN5180 firmware version (stub)");
        Ok((0, 0, 0))
    }

    /// Load RF configuration for ISO 14443A at 106 kbps.
    pub async fn load_iso14443a_config(&mut self) -> Result<(), Pn5180Error> {
        // TODO: Send LOAD_RF_CONFIG command
        info!("Loading ISO 14443A config (stub)");
        Ok(())
    }

    /// Turn RF field on.
    pub async fn rf_on(&mut self) -> Result<(), Pn5180Error> {
        // TODO: Send RF_ON command
        info!("RF field on (stub)");
        Ok(())
    }

    /// Turn RF field off.
    pub async fn rf_off(&mut self) -> Result<(), Pn5180Error> {
        // TODO: Send RF_OFF command
        info!("RF field off (stub)");
        Ok(())
    }

    /// Detect ISO 14443A card (REQA/WUPA).
    pub async fn iso14443a_detect(&mut self) -> Result<Option<Iso14443aCard>, Pn5180Error> {
        // TODO: Send REQA/WUPA, handle ATQA response
        info!("Detecting ISO 14443A card (stub)");
        Ok(None)
    }

    /// Select ISO 14443A card and get full UID.
    pub async fn iso14443a_select(&mut self, uid_partial: &[u8]) -> Result<Iso14443aCard, Pn5180Error> {
        // TODO: Perform anticollision and select
        info!("Selecting ISO 14443A card (stub)");
        Err(Pn5180Error::NoCard)
    }

    /// Authenticate MIFARE Classic sector.
    pub async fn mifare_authenticate(
        &mut self,
        block: u8,
        key_type: MifareKeyType,
        key: &[u8; 6],
        uid: &[u8],
    ) -> Result<(), Pn5180Error> {
        // TODO: Send MIFARE_AUTHENTICATE command
        info!("MIFARE authenticate block {} (stub)", block);
        Err(Pn5180Error::AuthFailed)
    }

    /// Read MIFARE Classic block (16 bytes).
    pub async fn mifare_read_block(&mut self, block: u8) -> Result<[u8; 16], Pn5180Error> {
        // TODO: Send READ command and receive data
        info!("MIFARE read block {} (stub)", block);
        Err(Pn5180Error::ReadFailed)
    }

    /// Read NTAG page (4 bytes).
    pub async fn ntag_read_page(&mut self, page: u8) -> Result<[u8; 4], Pn5180Error> {
        // TODO: Send READ command for NTAG
        info!("NTAG read page {} (stub)", page);
        Err(Pn5180Error::ReadFailed)
    }

    /// Write NTAG page (4 bytes).
    pub async fn ntag_write_page(&mut self, page: u8, data: &[u8; 4]) -> Result<(), Pn5180Error> {
        // TODO: Send WRITE command for NTAG
        info!("NTAG write page {} (stub)", page);
        Err(Pn5180Error::WriteFailed)
    }

    /// Low-level register read.
    async fn read_register(&mut self, reg: u8) -> Result<u32, Pn5180Error> {
        // TODO: Implement SPI read
        Ok(0)
    }

    /// Low-level register write.
    async fn write_register(&mut self, reg: u8, value: u32) -> Result<(), Pn5180Error> {
        // TODO: Implement SPI write
        Ok(())
    }
}

/// ISO 14443A card info
#[derive(Debug, Clone)]
pub struct Iso14443aCard {
    /// UID (4, 7, or 10 bytes)
    pub uid: heapless::Vec<u8, 10>,
    /// ATQA (2 bytes)
    pub atqa: [u8; 2],
    /// SAK byte
    pub sak: u8,
}

impl Iso14443aCard {
    /// Check if this is an NTAG (based on SAK)
    pub fn is_ntag(&self) -> bool {
        self.sak == 0x00
    }

    /// Check if this is a MIFARE Classic 1K (based on SAK)
    pub fn is_mifare_classic_1k(&self) -> bool {
        self.sak == 0x08
    }

    /// Check if this is a MIFARE Classic 4K (based on SAK)
    pub fn is_mifare_classic_4k(&self) -> bool {
        self.sak == 0x18
    }
}

/// PN5180 errors
#[derive(Debug, Clone, Copy)]
pub enum Pn5180Error {
    SpiError,
    Timeout,
    NoCard,
    AuthFailed,
    ReadFailed,
    WriteFailed,
    InvalidResponse,
}
