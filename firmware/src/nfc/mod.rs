//! NFC reader module for PN5180.
//!
//! The PN5180 is a high-performance NFC frontend IC that supports:
//! - ISO 14443 A/B (MIFARE, NTAG)
//! - ISO 15693
//! - ISO 18092 (NFC)
//!
//! Communication is via SPI.

pub mod pn5180;

use alloc::vec::Vec;
use log::info;

/// NFC tag types we support
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum NfcTagType {
    /// NTAG213/215/216 - used for SpoolEase tags
    Ntag,
    /// MIFARE Classic 1K - used for Bambu Lab tags
    MifareClassic1K,
    /// MIFARE Classic 4K
    MifareClassic4K,
    /// Unknown tag type
    Unknown,
}

/// Result of reading an NFC tag
#[derive(Debug, Clone)]
pub struct TagReadResult {
    /// Tag UID (4, 7, or 10 bytes)
    pub uid: Vec<u8>,
    /// Detected tag type
    pub tag_type: NfcTagType,
    /// NDEF URL (if NTAG with URL record)
    pub ndef_url: Option<Vec<u8>>,
    /// Raw NDEF message bytes
    pub ndef_message: Option<Vec<u8>>,
    /// MIFARE block data (if Bambu Lab tag)
    pub mifare_blocks: Option<Vec<(u8, Vec<u8>)>>,
}

/// NFC reader state
pub struct NfcReader {
    // TODO: Add SPI device handle
    // spi: SpiDevice,
    initialized: bool,
}

impl NfcReader {
    pub fn new() -> Self {
        Self {
            initialized: false,
        }
    }

    /// Initialize the PN5180 reader.
    pub async fn init(&mut self) -> Result<(), NfcError> {
        info!("Initializing PN5180 NFC reader (stub)");

        // TODO: Implement PN5180 initialization
        // 1. Reset the chip
        // 2. Read firmware version
        // 3. Configure for ISO 14443A
        // 4. Set RF field

        self.initialized = true;
        Ok(())
    }

    /// Wait for a tag to be detected and read its data.
    pub async fn wait_for_tag(&mut self) -> Result<TagReadResult, NfcError> {
        if !self.initialized {
            return Err(NfcError::NotInitialized);
        }

        info!("Waiting for NFC tag (stub)");

        // TODO: Implement tag detection
        // 1. Poll for ISO 14443A target
        // 2. Get UID and determine tag type
        // 3. Read NDEF or MIFARE data based on tag type

        Err(NfcError::NoTag)
    }

    /// Read NDEF message from an NTAG.
    pub async fn read_ndef(&mut self) -> Result<Option<Vec<u8>>, NfcError> {
        // TODO: Implement NDEF reading
        // 1. Read capability container
        // 2. Find NDEF TLV
        // 3. Read and parse NDEF message
        Ok(None)
    }

    /// Read Bambu Lab tag data (MIFARE Classic with Crypto-1).
    pub async fn read_bambulab_tag(&mut self, uid: &[u8]) -> Result<Vec<(u8, Vec<u8>)>, NfcError> {
        // TODO: Implement MIFARE Classic reading with Bambu Lab keys
        // 1. Authenticate with sector key
        // 2. Read data blocks
        // 3. Return block data map
        Err(NfcError::AuthFailed)
    }

    /// Write NDEF URL record to an NTAG.
    pub async fn write_ndef_url(&mut self, url: &str) -> Result<(), NfcError> {
        // TODO: Implement NDEF URL writing
        // 1. Format NDEF message with URL record
        // 2. Write to tag memory
        Err(NfcError::WriteFailed)
    }
}

/// NFC errors
#[derive(Debug, Clone, Copy)]
pub enum NfcError {
    NotInitialized,
    NoTag,
    CommunicationError,
    AuthFailed,
    ReadFailed,
    WriteFailed,
    UnsupportedTag,
}
