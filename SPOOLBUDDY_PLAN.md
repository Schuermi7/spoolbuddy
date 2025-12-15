# SpoolBuddy - Project Plan

> A smart filament management system for Bambu Lab 3D printers.
> Inspired by [SpoolEase](https://github.com/yanshay/SpoolEase) - built from scratch.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Hardware](#hardware)
4. [Software Components](#software-components)
5. [Development Phases](#development-phases)
6. [Technical Details](#technical-details)
7. [Upstream Sync Strategy](#upstream-sync-strategy)

---

## Project Overview

### What is SpoolBuddy?

SpoolBuddy is a reimagined filament management system that combines:
- **NFC-based spool identification** - Read/write tags on filament spools
- **Weight tracking** - Integrated scale for precise filament measurement
- **Inventory management** - Track all your spools, usage, and K-profiles
- **Automatic printer configuration** - Auto-configure AMS slots via MQTT

### Key Differences from SpoolEase

| Aspect | SpoolEase | SpoolBuddy |
|--------|-----------|--------------|
| Architecture | Standalone embedded | Server + ESP32 Device |
| Device | ESP32-S3 + 3.5" (480×320) | ESP32-S3 + 4.3" (800×480) |
| Console + Scale | Separate devices | Combined unit |
| Device UI | Slint (embedded) | LVGL (embedded) |
| Web UI | Embedded web server | Dedicated server (Preact) |
| Database | CSV on SD card | SQLite on server |
| NFC Reader | PN532 (~5cm range) | PN5180 (~20cm range) |
| Codebase | Reference only | Built from scratch |

### Goals

1. **Modern UI** - Professional web-based interface accessible from any device
2. **Easy updates** - Server updates don't require device reflashing
3. **Multi-device** - Same web UI on device, tablet, browser
4. **Maintainable** - Standard web stack, custom ESP32 firmware
5. **Independent** - No external code dependencies, fully owned codebase

---

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                      SERVER (Docker)                        │
│                                                             │
│  ┌──────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │Python Backend│  │   Web UI    │  │  Database   │        │
│  │  (FastAPI)   │  │  (Preact)   │  │  (SQLite)   │        │
│  │              │  │             │  │             │        │
│  │ • MQTT       │  │ • Inventory │  │ • Spools    │        │
│  │ • REST API   │  │ • Printers  │  │ • Printers  │        │
│  │ • WebSocket  │  │ • Dashboard │  │ • K-Values  │        │
│  │ • Tag decode │  │ • Settings  │  │ • History   │        │
│  └──────┬───────┘  └──────┬──────┘  └─────────────┘        │
│         │                 │                                 │
│         └─────────────────┘                                 │
│                  │                                          │
└──────────────────┼──────────────────────────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    │ HTTP/WS      │              │ WebSocket
    ▼              ▼              ▼
┌─────────┐  ┌─────────┐  ┌─────────────────────────────────┐
│ Browser │  │ Tablet  │  │      SpoolBuddy Device          │
│         │  │         │  │                                 │
│ Web UI  │  │ Web UI  │  │  ┌───────────────────────────┐  │
│         │  │         │  │  │  ESP32-S3-Touch-LCD-4.3   │  │
└─────────┘  └─────────┘  │  │  (Waveshare)              │  │
                          │  │                           │  │
                          │  │  • 4.3" 800×480 touch     │  │
                          │  │  • WiFi + BLE 5           │  │
                          │  │  • 8MB Flash, 8MB PSRAM   │  │
                          │  │  • Custom firmware (Rust) │  │
                          │  │                           │  │
                          │  │  Peripherals:             │  │
                          │  │  ├── PN5180 (SPI) - NFC   │  │
                          │  │  └── HX711 (GPIO) - Scale │  │
                          │  └───────────────────────────┘  │
                          │                                 │
                          │      ┌───────┐  ┌───────┐       │
                          │      │PN5180 │  │ Scale │       │
                          │      │  NFC  │  │ HX711 │       │
                          │      └───────┘  └───────┘       │
                          └─────────────────────────────────┘
```

### Communication Flow

```
ESP32 Device                    Server
     │                            │
     │◄────── WebSocket ─────────►│
     │        • Tag detected      │
     │        • Weight changed    │
     │        • Tag write cmd     │
     │        • Config sync       │
     │                            │
     │◄────── HTTP ──────────────►│
     │        • Web UI (browser)  │
     │        • OTA updates       │
     │                            │
```

---

## Hardware

### Device Components

| Component | Choice | Interface | Notes |
|-----------|--------|-----------|-------|
| **Main Board** | Waveshare ESP32-S3-Touch-LCD-4.3 | - | ESP32-S3, 8MB Flash, 8MB PSRAM |
| **Display** | Built-in 4.3" IPS | Parallel RGB | 800×480, 5-point capacitive touch |
| **NFC Reader** | PN5180 module | SPI | Extended range (~20cm), MIFARE Crypto1 support |
| **Scale** | HX711 + Load Cell | GPIO | Standard load cell setup |
| **Power** | USB-C 5V/2A | - | Single power input |

### ESP32-S3-Touch-LCD-4.3 Specifications

- **Processor**: Xtensa 32-bit LX7 dual-core, up to 240MHz
- **Memory**: 512KB SRAM, 384KB ROM, 8MB PSRAM, 8MB Flash
- **Wireless**: 2.4GHz WiFi (802.11 b/g/n), Bluetooth 5 (LE)
- **Display**: 4.3" IPS, 800×480, 65K colors, capacitive touch (I2C, 5-point)
- **Interfaces**: SPI, I2C, UART, CAN, RS485, USB, TF card slot
- **Wiki**: https://www.waveshare.com/wiki/ESP32-S3-Touch-LCD-4.3

### Hardware Sources

| Component | Source | Price | Status |
|-----------|--------|-------|--------|
| ESP32 Display | [Amazon.de](https://www.amazon.de/dp/B0CNZ6CHR7) | ~€45 | Ordered |
| NFC Reader | [LaskaKit.cz](https://www.laskakit.cz/en/rfid-ctecka-s-vestavenou-antenou-nfc-rf-pn5180-iso15693-cteni-i-zapis/) | €10.23 | Ordered |
| HX711 + Load Cell | TBD | ~€10 | TBD |

### GPIO Pin Allocation

```
ESP32-S3-Touch-LCD-4.3 GPIO (directly from connectors):

PN5180 (SPI - directly on expansion header):
  - MOSI: GPIO 11
  - MISO: GPIO 13
  - SCLK: GPIO 12
  - NSS:  GPIO 10
  - BUSY: GPIO 14
  - RST:  GPIO 21

HX711 (Scale - directly on expansion header):
  - DT:   GPIO 1
  - SCK:  GPIO 2

Note: Pin assignments TBD based on available GPIOs on expansion connectors.
      Check Waveshare wiki for actual pinout.
```

### Physical Design

- Combined Console + Scale in single case
- NFC antenna (PN5180) positioned under scale platform center
- Spool sits on platform, center hole aligns with NFC reader
- Extended NFC range (~20cm) enables reading Bambu Lab tags inside spool core
- 4.3" display angled for visibility
- Single USB-C power input

---

## Software Components

### 1. Server Backend (Python)

**Framework:** FastAPI + Uvicorn

**Responsibilities:**
- REST API for web UI
- WebSocket for device communication
- MQTT client for Bambu Lab printers
- Tag encoding/decoding (SpoolEase, Bambu Lab, OpenPrintTag formats)
- Database operations (SQLite)
- Serve static web UI

**Structure:**
```
backend/
├── main.py           # FastAPI app, WebSocket handler
├── config.py         # Settings
├── models.py         # Pydantic models
├── api/              # REST API routes
│   ├── spools.py
│   └── printers.py
├── db/               # Database layer
│   └── database.py
├── mqtt/             # Printer MQTT client
│   ├── client.py
│   └── bambu_api.rs  # Message structures
└── tags/             # NFC tag encoding/decoding
    ├── spoolease.py
    ├── bambulab.py
    └── openprinttag.py
```

### 2. Web UI (Preact + TypeScript)

**Framework:** Preact + Vite + TailwindCSS

**Pages:**
- **Dashboard** - Overview, printer status, current print
- **Inventory** - Spool list, search, filter
- **Printers** - Printer configuration, AMS status
- **Spool Detail** - Edit spool, K-profiles, history
- **Settings** - Server config, device settings

**Features:**
- Responsive design (desktop, tablet, device screen)
- Real-time updates via WebSocket
- Works in browser and on device's built-in display

### 3. Device Firmware (Rust/ESP32)

**Target:** ESP32-S3-Touch-LCD-4.3 (Waveshare)

**Framework:** esp-hal + embassy (async)

**Responsibilities:**
- Read NFC tags (PN5180 via SPI)
- Read scale weight (HX711 via GPIO)
- Display UI (LVGL or custom)
- WiFi connection to server
- WebSocket communication
- Local display of spool info, weight, status

**Structure:**
```
firmware/
├── Cargo.toml
├── src/
│   ├── main.rs         # Entry point, task spawning
│   ├── wifi.rs         # WiFi connection
│   ├── websocket.rs    # Server communication
│   ├── nfc/
│   │   ├── mod.rs
│   │   └── pn5180.rs   # PN5180 driver
│   ├── scale/
│   │   ├── mod.rs
│   │   └── hx711.rs    # HX711 driver
│   └── ui/
│       ├── mod.rs
│       └── screens.rs  # LVGL screens
└── build.rs
```

**Key Crates:**
- `esp-hal` - ESP32-S3 hardware abstraction
- `embassy-executor` - Async runtime
- `embassy-net` - Networking
- `embedded-graphics` or `lvgl` - UI rendering

---

## Development Phases

### Phase 1: Foundation ✅ Complete

**Goal:** Basic working system, prove architecture

**Server:**
- [x] FastAPI server with REST API
- [x] SQLite database schema and migrations
- [x] Spool CRUD operations
- [x] WebSocket endpoint for UI updates
- [x] Static file serving for web UI

**Web UI:**
- [x] Inventory page with search/filter
- [x] Spool detail/edit modal
- [x] Stats bar with inventory overview
- [x] WebSocket integration for live updates

**Deliverable:** Can view/edit spools via web UI

### Phase 2: Printer Integration ✅ Complete

**Goal:** Connect to Bambu Lab printers via MQTT

**Server:**
- [x] MQTT client for printer communication
- [x] Printer state tracking (print status, AMS data)
- [x] AMS slot configuration commands
- [x] K-profile selection per slot
- [x] RFID re-read trigger (`ams_get_rfid`)
- [x] Tag encoding/decoding (SpoolEase V2, Bambu Lab, OpenPrintTag)

**Web UI:**
- [x] Printer management page (add/edit/delete)
- [x] Real-time printer status display
- [x] AMS slot visualization with colors, materials, K-values
- [x] Active tray indicator
- [x] Slot context menu (re-read RFID, select K-profile)

**Deliverable:** Full printer MQTT integration with AMS control

### Phase 3: Device Firmware 🔄 Next

**Goal:** ESP32-S3 firmware for NFC + Scale

**Firmware:**
- [ ] Project setup (esp-hal + embassy)
- [ ] WiFi connection and config portal
- [ ] WebSocket client to server
- [ ] PN5180 NFC driver (SPI)
- [ ] HX711 scale driver (GPIO)
- [ ] Basic LVGL UI (weight display, status)
- [ ] Tag read → WebSocket → Server flow

**Server:**
- [x] WebSocket handler for tag_detected messages
- [x] Tag decoding and spool matching
- [ ] Tag write command handling

**Deliverable:** Device reads NFC tags and weight, sends to server

### Phase 4: Filament Tracking

**Goal:** Track filament usage during prints

**Server:**
- [ ] G-code analysis for filament usage
- [ ] FTP client for printer file access
- [ ] Real-time usage tracking during print
- [ ] Consumption history per spool

**Web UI:**
- [ ] Print progress display
- [ ] Usage history graphs
- [ ] Low stock warnings

**Deliverable:** Accurate filament tracking, usage history

### Phase 5: K-Profile Management

**Goal:** Full pressure advance calibration management

**Server:**
- [ ] K-profile storage per spool/printer/nozzle
- [ ] Auto-restore K values when loading spool
- [ ] Import K values from printer

**Web UI:**
- [ ] K-profile editor
- [ ] Per-printer/nozzle configuration

**Deliverable:** Full pressure advance management

### Phase 6: NFC Writing & Advanced Features

**Goal:** Complete feature set

**Firmware:**
- [ ] NFC tag writing (SpoolEase V2 format)
- [ ] Scale calibration
- [ ] Offline mode with sync

**Server:**
- [ ] Tag write command generation
- [ ] Backup/restore functionality

**Web UI:**
- [ ] Tag encoding page
- [ ] Backup/restore UI
- [ ] Settings page

**Deliverable:** Full-featured filament management

### Phase 7: Polish & Documentation

**Goal:** Production ready

- [ ] Error handling and edge cases
- [ ] Performance optimization
- [ ] User documentation
- [ ] Installation guide
- [ ] Docker compose setup
- [ ] Firmware build/flash instructions

---

## Technical Details

### Database Schema (SQLite)

```sql
-- Spools table
CREATE TABLE spools (
    id TEXT PRIMARY KEY,
    tag_id TEXT UNIQUE,
    material TEXT NOT NULL,
    subtype TEXT,
    color_name TEXT,
    rgba TEXT,
    brand TEXT,
    label_weight INTEGER DEFAULT 1000,
    core_weight INTEGER DEFAULT 250,
    weight_new INTEGER,
    weight_current INTEGER,
    slicer_filament TEXT,
    note TEXT,
    added_time INTEGER,
    encode_time INTEGER,
    added_full BOOLEAN DEFAULT FALSE,
    consumed_since_add REAL DEFAULT 0,
    consumed_since_weight REAL DEFAULT 0,
    data_origin TEXT,
    tag_type TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER DEFAULT (strftime('%s', 'now'))
);

-- Printers table
CREATE TABLE printers (
    serial TEXT PRIMARY KEY,
    name TEXT,
    model TEXT,
    ip_address TEXT,
    access_code TEXT,
    last_seen INTEGER,
    config JSON
);

-- K-Profiles table
CREATE TABLE k_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spool_id TEXT REFERENCES spools(id),
    printer_serial TEXT REFERENCES printers(serial),
    extruder INTEGER,
    nozzle_diameter TEXT,
    nozzle_type TEXT,
    k_value TEXT,
    name TEXT,
    cali_idx INTEGER,
    setting_id TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
);

-- Usage history table
CREATE TABLE usage_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spool_id TEXT REFERENCES spools(id),
    printer_serial TEXT,
    print_name TEXT,
    weight_used REAL,
    timestamp INTEGER DEFAULT (strftime('%s', 'now'))
);
```

### WebSocket Protocol

**Device → Server:**

```json
// Tag detected
{
    "type": "tag_detected",
    "tag_id": "04:AB:CD:EF:12:34:56",
    "tag_type": "ntag215",
    "data": { /* parsed tag data */ }
}

// Tag removed
{
    "type": "tag_removed"
}

// Weight update
{
    "type": "weight",
    "grams": 1234.5,
    "stable": true
}

// Heartbeat
{
    "type": "heartbeat",
    "uptime": 12345
}
```

**Server → Device:**

```json
// Write tag command
{
    "type": "write_tag",
    "request_id": "abc123",
    "data": { /* tag data to write */ }
}

// Tare scale
{
    "type": "tare_scale"
}

// Calibrate scale
{
    "type": "calibrate_scale",
    "known_weight": 500
}

// Show notification on device
{
    "type": "notification",
    "message": "Spool loaded: PLA Red",
    "duration": 3000
}
```

### REST API Endpoints

```
GET    /api/spools              - List all spools
POST   /api/spools              - Create spool
GET    /api/spools/:id          - Get spool
PUT    /api/spools/:id          - Update spool
DELETE /api/spools/:id          - Delete spool

GET    /api/printers            - List printers
POST   /api/printers            - Add printer
GET    /api/printers/:serial    - Get printer
PUT    /api/printers/:serial    - Update printer
DELETE /api/printers/:serial    - Remove printer

GET    /api/k-profiles/:spool   - Get K-profiles for spool
POST   /api/k-profiles          - Save K-profile
DELETE /api/k-profiles/:id      - Delete K-profile

GET    /api/device/status       - Device connection status
POST   /api/device/tare         - Tare scale
POST   /api/device/write-tag    - Write NFC tag

WS     /ws/device               - Device WebSocket
WS     /ws/ui                   - UI WebSocket (live updates)
```

### Project Structure

```
spoolbuddy/
├── backend/                    # Python server
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── requirements.txt
│   ├── api/
│   │   ├── __init__.py
│   │   ├── spools.py
│   │   └── printers.py
│   ├── db/
│   │   ├── __init__.py
│   │   └── database.py
│   ├── mqtt/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   └── bambu_api.py
│   └── tags/
│       ├── __init__.py
│       ├── models.py
│       ├── decoder.py
│       ├── spoolease.py
│       ├── bambulab.py
│       └── openprinttag.py
│
├── web/                        # Preact frontend
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── components/
│   │   ├── pages/
│   │   └── lib/
│   └── public/
│
├── firmware/                   # ESP32-S3 firmware (Rust)
│   ├── Cargo.toml
│   ├── src/
│   │   ├── main.rs
│   │   ├── wifi.rs
│   │   ├── websocket.rs
│   │   ├── nfc/
│   │   │   └── pn5180.rs
│   │   ├── scale/
│   │   │   └── hx711.rs
│   │   └── ui/
│   │       └── screens.rs
│   └── build.rs
│
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── SPOOLBUDDY_PLAN.md
├── CLAUDE.md
├── LICENSE
└── README.md
```

---

## Next Steps

**Current:** Phase 3 - Device Firmware

1. Set up ESP32-S3 Rust project with esp-hal
2. Implement WiFi connection
3. Implement PN5180 NFC driver
4. Implement HX711 scale driver
5. WebSocket client to server
6. Basic UI for weight/status display

---

*Document created: December 2024*
*Last updated: December 2024*
*Inspired by SpoolEase - built from scratch*
