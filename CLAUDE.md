# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

SpoolBuddy is a filament management system for Bambu Lab 3D printers. It provides:
- NFC-based spool identification (planned)
- Weight scale integration for filament tracking (planned)
- Inventory management and spool catalog
- MQTT-based printer connectivity with AMS visualization

## Repository Structure

```
SpoolBuddy/
├── backend/           # Python FastAPI server
│   ├── main.py        # Entry point
│   ├── config.py      # Configuration
│   ├── models.py      # Pydantic models
│   ├── db/            # Database layer (SQLite)
│   ├── mqtt/          # Bambu printer MQTT client
│   └── api/           # REST API endpoints
├── frontend/          # Preact web UI
│   ├── src/
│   │   ├── pages/     # Page components
│   │   ├── components/# Reusable components
│   │   └── lib/       # Utilities, WebSocket client
│   └── dist/          # Built static files
└── spoolease_sources/ # Reference: original SpoolEase ESP32 code
```

## Development Commands

### Backend (Python)

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run development server
python main.py
# or: uvicorn main:app --reload --port 3000
```

### Frontend (Node.js)

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build
```

### Running Both

1. Start backend: `cd backend && python main.py`
2. For development: `cd frontend && npm run dev` (proxies to backend)
3. For production: Build frontend, backend serves static files

## API Endpoints

- `GET /api/spools` - List all spools
- `POST /api/spools` - Create spool
- `GET /api/spools/{id}` - Get spool
- `PUT /api/spools/{id}` - Update spool
- `DELETE /api/spools/{id}` - Delete spool

- `GET /api/printers` - List printers with status
- `POST /api/printers` - Create/update printer
- `POST /api/printers/{serial}/connect` - Connect to printer
- `POST /api/printers/{serial}/disconnect` - Disconnect

- `WS /ws/ui` - WebSocket for real-time updates

## Bambu MQTT Protocol Notes

- Printers use MQTT over TLS on port 8883
- Username: `bblp`, Password: printer's access code
- Subscribe to: `device/{serial}/report`
- Publish to: `device/{serial}/request`
- AMS IDs: 0-3 = AMS A-D, 128-135 = AMS HT A-H, 254/255 = External

## Reference Material

The `spoolease_sources/` directory contains the original SpoolEase embedded code.
Use it as reference documentation for:
- Bambu MQTT message formats
- AMS data structures
- NFC tag encoding (SpoolEase format)

Do NOT port this code directly - it's ESP32 embedded Rust (`no_std`).
