from fastapi import APIRouter, HTTPException
import logging

from db import get_db
from models import Printer, PrinterCreate, PrinterUpdate, PrinterWithStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/printers", tags=["printers"])

# Reference to printer manager (set by main.py)
_printer_manager = None


def set_printer_manager(manager):
    """Set the printer manager reference."""
    global _printer_manager
    _printer_manager = manager


@router.get("", response_model=list[PrinterWithStatus])
async def list_printers():
    """Get all printers with connection status."""
    db = await get_db()
    printers = await db.get_printers()

    # Get connection statuses
    statuses = _printer_manager.get_connection_statuses() if _printer_manager else {}

    return [
        PrinterWithStatus(
            **printer.model_dump(),
            connected=statuses.get(printer.serial, False)
        )
        for printer in printers
    ]


@router.get("/{serial}", response_model=PrinterWithStatus)
async def get_printer(serial: str):
    """Get a single printer."""
    db = await get_db()
    printer = await db.get_printer(serial)
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")

    connected = _printer_manager.is_connected(serial) if _printer_manager else False
    return PrinterWithStatus(**printer.model_dump(), connected=connected)


@router.post("", response_model=Printer, status_code=201)
async def create_printer(printer: PrinterCreate):
    """Create or update a printer."""
    db = await get_db()
    return await db.create_printer(printer)


@router.put("/{serial}", response_model=Printer)
async def update_printer(serial: str, printer: PrinterUpdate):
    """Update an existing printer."""
    db = await get_db()
    updated = await db.update_printer(serial, printer)
    if not updated:
        raise HTTPException(status_code=404, detail="Printer not found")
    return updated


@router.delete("/{serial}", status_code=204)
async def delete_printer(serial: str):
    """Delete a printer."""
    # Disconnect first
    if _printer_manager:
        await _printer_manager.disconnect(serial)

    db = await get_db()
    if not await db.delete_printer(serial):
        raise HTTPException(status_code=404, detail="Printer not found")


@router.post("/{serial}/connect", status_code=204)
async def connect_printer(serial: str):
    """Connect to a printer."""
    if not _printer_manager:
        raise HTTPException(status_code=500, detail="Printer manager not available")

    db = await get_db()
    printer = await db.get_printer(serial)
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")

    if not printer.ip_address or not printer.access_code:
        raise HTTPException(status_code=400, detail="Printer missing IP address or access code")

    try:
        await _printer_manager.connect(
            serial=printer.serial,
            ip_address=printer.ip_address,
            access_code=printer.access_code,
            name=printer.name,
        )
    except Exception as e:
        logger.error(f"Failed to connect to {serial}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{serial}/disconnect", status_code=204)
async def disconnect_printer(serial: str):
    """Disconnect from a printer."""
    if _printer_manager:
        await _printer_manager.disconnect(serial)


@router.post("/{serial}/auto-connect", response_model=Printer)
async def toggle_auto_connect(serial: str):
    """Toggle auto-connect setting."""
    db = await get_db()
    printer = await db.get_printer(serial)
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")

    return await db.update_printer(serial, PrinterUpdate(auto_connect=not printer.auto_connect))
