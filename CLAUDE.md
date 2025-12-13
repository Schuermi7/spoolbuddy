# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SpoolEase is a smart add-on system for Bambu Lab 3D printers that provides NFC-based spool identification, inventory management, and precise filament tracking via weight scale and print usage monitoring. It supports X1, P1, A1, H2, P2 product lines with various AMS configurations.

The system has two products:
- **SpoolEase Console** - Main hub with display, NFC encoding, inventory tracking, printer setup
- **SpoolEase Scale** - Weight measurement device (requires Console)

## Repository Structure

- **core/** - ESP32-S3 embedded Rust firmware for the Console (main application)
- **shared/** - Shared Rust library used by core (NFC handling, gcode analysis, FTP client, etc.)
- **new/src/inventory/** - Preact/TypeScript web-based inventory management UI

## Build Commands

### Core Firmware (Rust/ESP32-S3)

Requires the ESP Rust toolchain (`esp` channel).

```bash
cd core

# Build debug
cargo build

# Build release
cargo build --release

# Flash and monitor (uses espflash with 16MB flash config)
cargo run --release
```

The flash configuration is in `core/.cargo/config.toml` - 16MB flash, DIO mode, 80MHz.

### Inventory Web UI

```bash
cd new/src/inventory

npm install
npm run dev      # Development server
npm run build    # Production build (outputs to static for embedding)
npm run lint     # ESLint check
```

### Deploy Scripts

Located in `core/`:
- `deploy-beta.sh` - Deploy to beta/unstable OTA channel
- `deploy-rel.sh` - Deploy to release OTA channel
- `deploy-debug.sh` - Debug deployment

These scripts require the `esp-hal-app` xtask tooling and `spoolease-bin` output directory to be available in parent directories.

## Architecture

### Core Firmware (`core/src/`)

The firmware is a `no_std` embedded Rust application for ESP32-S3 using:
- **esp-hal** ecosystem (esp-hal, esp-wifi, esp-mbedtls, embassy)
- **Slint** for touch UI (`.slint` files in `core/ui/`)
- **esp-hal-app-framework** - Custom framework for WiFi, display, settings management

Key modules:
- `main.rs` - Entry point, hardware init, task spawning
- `bambu.rs` / `bambu_api.rs` - Bambu Lab printer communication via MQTT
- `view_model.rs` - UI state management and business logic
- `store.rs` - Persistent storage for spools, printers, settings
- `spool_scale.rs` - Scale communication and weight tracking
- `web_app.rs` - Embedded web server for configuration and inventory API
- `my_mqtt.rs` - MQTT client for printer communication

### Shared Library (`shared/src/`)

Reusable components:
- `spool_tag.rs` - NFC tag data encoding/decoding
- `pn532_ext.rs` - PN532 NFC reader extensions
- `gcode_analysis.rs` / `gcode_analysis_task.rs` - Print file analysis
- `my_ftp.rs` - FTP client for printer file access
- `threemf_extractor.rs` - 3MF file parsing

### UI Layer

- `core/ui/*.slint` - Slint UI definitions
- `core/static/` - Web assets served by embedded web server
- `new/src/inventory/` - Standalone inventory web app (Preact + TailwindCSS)

## Development Notes

- Target: `xtensa-esp32s3-none-elf`
- Uses PSRAM for heap allocation
- Nightly Rust features required (see `#![feature(...)]` in main.rs)
- TLS certificates for Bambu Lab and OTA in `core/src/certs/`
- Configuration data (filament brands, materials, spool weights) in `core/data/*.csv`
