#!/bin/bash
# SpoolBuddy Firmware Flash Script
# Uses espflash 2.1.0 which handles bootloader automatically

set -e

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Re-running with sudo..."
    exec sudo "$0" "$@"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# ESP32-S3 target (Waveshare ESP32-S3-Touch-LCD-4.3)
FIRMWARE_ELF="$SCRIPT_DIR/target/xtensa-esp32s3-none-elf/release/spoolbuddy-firmware"
PORT="${1:-/dev/ttyACM0}"

echo "========================================"
echo "  SpoolBuddy Firmware Flash Script"
echo "========================================"

# Check if firmware exists
if [ ! -f "$FIRMWARE_ELF" ]; then
    echo "Error: Firmware not found. Run 'cargo build --release' first."
    exit 1
fi

# Find espflash (handle sudo environment)
ESPFLASH="${HOME}/.cargo/bin/espflash"
if [ ! -f "$ESPFLASH" ]; then
    ESPFLASH="/opt/claude/.cargo/bin/espflash"
fi
if [ ! -f "$ESPFLASH" ]; then
    ESPFLASH=$(which espflash 2>/dev/null || echo "")
fi
if [ -z "$ESPFLASH" ] || [ ! -f "$ESPFLASH" ]; then
    echo "Error: espflash not found. Install with: cargo install espflash"
    exit 1
fi
echo "Using espflash: $ESPFLASH"
echo "Firmware: $FIRMWARE_ELF"
echo "Port: $PORT"
echo ""

# Flash using espflash (handles bootloader automatically)
echo "Flashing firmware..."
sudo $ESPFLASH flash --monitor --port "$PORT" "$FIRMWARE_ELF"
