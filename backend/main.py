import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from db import get_db
from mqtt import PrinterManager
from api import spools_router, printers_router
from api.printers import set_printer_manager
from models import PrinterState

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global state
printer_manager = PrinterManager()
websocket_clients: Set[WebSocket] = set()


async def broadcast_message(message: dict):
    """Broadcast message to all connected WebSocket clients."""
    if not websocket_clients:
        return

    text = json.dumps(message)
    disconnected = set()

    for ws in websocket_clients:
        try:
            await ws.send_text(text)
        except Exception:
            disconnected.add(ws)

    # Clean up disconnected clients
    websocket_clients.difference_update(disconnected)


def on_printer_state_update(serial: str, state: PrinterState):
    """Handle printer state update from MQTT."""
    # Convert to dict for JSON serialization
    message = {
        "type": "printer_state",
        "serial": serial,
        "state": state.model_dump(),
    }

    # Schedule broadcast in event loop
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast_message(message))
    except RuntimeError:
        pass  # No running loop


async def auto_connect_printers():
    """Connect to printers with auto_connect enabled."""
    await asyncio.sleep(0.5)  # Wait for startup

    db = await get_db()
    printers = await db.get_auto_connect_printers()

    for printer in printers:
        if printer.ip_address and printer.access_code:
            logger.info(f"Auto-connecting to printer {printer.serial}")
            try:
                await printer_manager.connect(
                    serial=printer.serial,
                    ip_address=printer.ip_address,
                    access_code=printer.access_code,
                    name=printer.name,
                )
            except Exception as e:
                logger.error(f"Failed to auto-connect to {printer.serial}: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting SpoolBuddy server...")

    # Initialize database
    await get_db()
    logger.info("Database initialized")

    # Set up printer manager
    set_printer_manager(printer_manager)
    printer_manager.set_state_callback(on_printer_state_update)

    # Auto-connect printers
    asyncio.create_task(auto_connect_printers())

    yield

    # Shutdown
    logger.info("Shutting down...")
    await printer_manager.disconnect_all()


# Create FastAPI app
app = FastAPI(
    title="SpoolBuddy",
    description="Filament management for Bambu Lab printers",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(spools_router, prefix="/api")
app.include_router(printers_router, prefix="/api")


@app.websocket("/ws/ui")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time UI updates."""
    await websocket.accept()
    websocket_clients.add(websocket)
    logger.info("WebSocket client connected")

    try:
        while True:
            # Keep connection alive, handle any incoming messages
            data = await websocket.receive_text()
            # Could handle commands from UI here
            logger.debug(f"Received from WebSocket: {data}")
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        websocket_clients.discard(websocket)


# Mount static files (frontend) - must be last
if settings.static_dir.exists():
    app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
