"""Shared test fixtures for SpoolBuddy backend tests."""

import asyncio
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set test environment before imports
os.environ["SPOOLBUDDY_DATABASE_PATH"] = ":memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db():
    """Create a test database with temporary file."""
    from db.database import Database

    # Use a temporary file for the database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    db = Database(db_path)
    await db.connect()

    yield db

    await db.disconnect()
    # Clean up temp file
    try:
        db_path.unlink()
    except Exception:
        pass


@pytest.fixture
def mock_printer_manager():
    """Mock the printer manager for API tests requiring MQTT."""
    from api import printers as printers_api

    manager = MagicMock()
    manager.is_connected = MagicMock(return_value=False)
    manager.connect = AsyncMock()
    manager.disconnect = AsyncMock()
    manager.get_state = MagicMock(return_value=None)
    manager.get_connection_statuses = MagicMock(return_value={})
    manager.set_filament = MagicMock(return_value=True)
    manager.set_calibration = MagicMock(return_value=True)
    manager.set_k_value = MagicMock(return_value=True)
    manager.reset_slot = MagicMock(return_value=True)
    manager.get_kprofiles = AsyncMock(return_value=[])
    manager.get_nozzle_diameter = MagicMock(return_value="0.4")
    manager.stage_assignment = MagicMock(return_value=True)
    manager.cancel_assignment = MagicMock(return_value=True)
    manager.get_all_pending_assignments = MagicMock(return_value={})

    # Set the mock as the global printer manager
    original = printers_api._printer_manager
    printers_api._printer_manager = manager

    yield manager

    # Restore original
    printers_api._printer_manager = original


@pytest.fixture
async def async_client(test_db, mock_printer_manager) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with test database."""
    from main import app
    from db import get_db

    # Override database dependency
    async def override_get_db():
        return test_db

    # Patch the global db getter
    with patch("db.get_db", override_get_db), \
         patch("db.database.get_db", override_get_db), \
         patch("api.spools.get_db", override_get_db), \
         patch("api.printers.get_db", override_get_db), \
         patch("api.cloud.get_db", override_get_db):

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            yield client


# ============================================================================
# Mock External Services
# ============================================================================

@pytest.fixture
def mock_mqtt_client():
    """Mock the MQTT client for printer communication tests."""
    with patch("mqtt.PrinterManager") as mock:
        instance = MagicMock()
        instance.is_connected = MagicMock(return_value=False)
        instance.connect = AsyncMock()
        instance.disconnect = AsyncMock()
        instance.get_state = MagicMock(return_value=None)
        mock.return_value = instance
        yield instance


@pytest.fixture
def mock_httpx_client():
    """Mock httpx for external HTTP calls."""
    with patch("httpx.AsyncClient") as mock_class:
        mock_instance = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_response.json.return_value = {}

        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_instance.post = AsyncMock(return_value=mock_response)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock()

        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_cloud_service():
    """Mock the Bambu Cloud service."""
    with patch("services.bambu_cloud.get_cloud_service") as mock:
        service = MagicMock()
        service.is_authenticated = False
        service.access_token = None
        service.login_request = AsyncMock(return_value={
            "success": False,
            "needs_verification": True,
            "message": "Verification code sent"
        })
        service.verify_code = AsyncMock(return_value={
            "success": True,
            "message": "Login successful"
        })
        service.set_token = MagicMock()
        service.logout = MagicMock()
        service.get_slicer_settings = AsyncMock(return_value={
            "filament": {"private": [], "public": []},
            "printer": {"private": [], "public": []},
            "print": {"private": [], "public": []},
        })
        mock.return_value = service
        yield service


# ============================================================================
# Factory Fixtures for Test Data
# ============================================================================

@pytest.fixture
def spool_factory(test_db):
    """Factory to create test spools."""
    async def _create_spool(**kwargs):
        from models import SpoolCreate

        defaults = {
            "material": "PLA",
            "color_name": "Black",
            "rgba": "#000000FF",
            "brand": "Bambu Lab",
            "label_weight": 1000,
            "core_weight": 250,
        }
        defaults.update(kwargs)

        spool_data = SpoolCreate(**defaults)
        return await test_db.create_spool(spool_data)

    return _create_spool


@pytest.fixture
def printer_factory(test_db):
    """Factory to create test printers."""
    _counter = [0]

    async def _create_printer(**kwargs):
        from models import PrinterCreate

        _counter[0] += 1
        counter = _counter[0]

        defaults = {
            "serial": f"00M09A{counter:09d}",
            "name": f"Test Printer {counter}",
            "model": "X1C",
            "ip_address": f"192.168.1.{100 + counter}",
            "access_code": "12345678",
            "auto_connect": False,
        }
        defaults.update(kwargs)

        printer_data = PrinterCreate(**defaults)
        return await test_db.create_printer(printer_data)

    return _create_printer


# ============================================================================
# Sample Data Fixtures
# ============================================================================

@pytest.fixture
def sample_spool_data():
    """Sample spool input data."""
    return {
        "material": "PETG",
        "subtype": "Basic",
        "color_name": "Red",
        "rgba": "#FF0000FF",
        "brand": "Bambu Lab",
        "label_weight": 1000,
        "core_weight": 250,
        "weight_new": 1000,
        "weight_current": 800,
        "slicer_filament": "GFPG99",
    }


@pytest.fixture
def sample_printer_data():
    """Sample printer input data."""
    return {
        "serial": "00M09A123456789",
        "name": "My X1 Carbon",
        "model": "X1C",
        "ip_address": "192.168.1.100",
        "access_code": "12345678",
        "auto_connect": True,
    }


# ============================================================================
# Log Capture Fixtures
# ============================================================================

class LogCapture(logging.Handler):
    """Handler that captures log records for testing."""

    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord):
        self.records.append(record)

    def clear(self):
        self.records.clear()

    def get_errors(self) -> list[logging.LogRecord]:
        """Get all ERROR and CRITICAL level records."""
        return [r for r in self.records if r.levelno >= logging.ERROR]

    def has_errors(self) -> bool:
        """Check if any errors were logged."""
        return len(self.get_errors()) > 0

    def format_errors(self) -> str:
        """Format all errors as a string for assertion messages."""
        errors = self.get_errors()
        if not errors:
            return "No errors"
        formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
        return "\n".join(formatter.format(r) for r in errors)


@pytest.fixture
def capture_logs():
    """Fixture that captures log output during a test."""
    handler = LogCapture()
    handler.setLevel(logging.DEBUG)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    yield handler

    root_logger.removeHandler(handler)


# ============================================================================
# MQTT Test Fixtures
# ============================================================================

@pytest.fixture
def sample_mqtt_report():
    """Sample Bambu MQTT print report."""
    return {
        "print": {
            "gcode_state": "RUNNING",
            "mc_percent": 45,
            "layer_num": 50,
            "total_layer_num": 200,
            "subtask_name": "test_print.gcode",
            "mc_remaining_time": 45,
            "gcode_file": "/sdcard/test_print.gcode",
            "ams": {
                "ams": [{
                    "id": "0",
                    "humidity": "35",
                    "humidity_raw": "42",
                    "temp": "25.5",
                    "tray": [
                        {
                            "id": "0",
                            "tray_type": "PLA",
                            "tray_color": "FF0000FF",
                            "tray_info_idx": "GFSL05",
                            "k": 0.025,
                            "remain": 80,
                            "nozzle_temp_min": 190,
                            "nozzle_temp_max": 230,
                        },
                        {
                            "id": "1",
                            "tray_type": "PETG",
                            "tray_color": "00FF00FF",
                            "tray_info_idx": "GFPG99",
                            "k": 0.035,
                            "remain": 50,
                            "nozzle_temp_min": 220,
                            "nozzle_temp_max": 260,
                        },
                        {
                            "id": "2",
                            "tray_type": "",
                            "tray_color": "",
                        },
                        {
                            "id": "3",
                            "tray_type": "ABS",
                            "tray_color": "0000FFFF",
                            "tray_info_idx": "GFSA00",
                            "k": 0.040,
                            "remain": 20,
                            "nozzle_temp_min": 240,
                            "nozzle_temp_max": 280,
                        },
                    ]
                }],
                "tray_now": "0",
            },
        }
    }


@pytest.fixture
def sample_dual_nozzle_report():
    """Sample MQTT report for dual-nozzle printer (H2C/H2D).

    Snow encoding: (ams_id << 8) | slot_id
    - 0x0001 = ams 0, slot 1 -> global tray = 1
    - 0x0102 = ams 1, slot 2 -> global tray = 6
    """
    return {
        "print": {
            "gcode_state": "RUNNING",
            "mc_percent": 60,
            "device": {
                "extruder": {
                    "info": [
                        {"id": 0, "dia": 0.4, "snow": 1},    # Right nozzle: ams 0, slot 1
                        {"id": 1, "dia": 0.6, "snow": 258},  # Left nozzle: ams 1, slot 2 (0x0102)
                    ],
                    "state": 16,  # Active extruder in bits 4-7 -> (16 >> 4) & 0xF = 1
                }
            },
            "ams": {
                "ams": [
                    {
                        "id": "0",
                        "humidity": "30",
                        "temp": "24.0",
                        "info": "0",  # Bit 8=0 means left extruder
                        "tray": [
                            {"id": "0", "tray_type": "PLA", "tray_color": "FFFFFFFF"},
                            {"id": "1", "tray_type": "PETG", "tray_color": "00FF00FF"},
                        ],
                    },
                    {
                        "id": "1",
                        "humidity": "28",
                        "temp": "24.5",
                        "info": "256",  # Bit 8=1 means right extruder
                        "tray": [
                            {"id": "0", "tray_type": "ABS", "tray_color": "0000FFFF"},
                            {"id": "1", "tray_type": "ASA", "tray_color": "FF00FFFF"},
                            {"id": "2", "tray_type": "TPU", "tray_color": "FFFF00FF"},
                        ],
                    },
                ],
                "tray_now": "255",  # No legacy tray_now for dual nozzle
            },
        }
    }


@pytest.fixture
def sample_calibration_profiles():
    """Sample K-value calibration profiles from extrusion_cali_get."""
    return [
        {
            "cali_idx": 42,
            "name": "Bambu PLA Basic",
            "k_value": "0.025",
            "filament_id": "GFSL05",
            "extruder_id": 0,
            "setting_id": "GFSL05_07",
        },
        {
            "cali_idx": 43,
            "name": "Bambu PLA Basic",
            "k_value": "0.025",
            "filament_id": "GFSL05",
            "extruder_id": 1,
            "setting_id": "GFSL05_07",
        },
        {
            "cali_idx": 44,
            "name": "Generic PETG",
            "k_value": "0.035",
            "filament_id": "GFPG99",
            "extruder_id": 0,
            "setting_id": "GFPG99_01",
        },
    ]


@pytest.fixture
def sample_slicer_settings():
    """Sample slicer settings from Bambu Cloud API."""
    return {
        "filament": {
            "private": [
                {
                    "setting_id": "custom-pla-001",
                    "name": "My Custom PLA",
                    "version": "01.09.00.06",
                    "user_id": "user123",
                },
            ],
            "public": [
                {
                    "setting_id": "GFSL05_07",
                    "name": "Bambu PLA Basic @BBL X1C",
                    "version": "01.09.00.06",
                },
                {
                    "setting_id": "GFPG99_01",
                    "name": "Generic PETG @BBL X1C",
                    "version": "01.09.00.06",
                },
            ],
        },
        "printer": {"private": [], "public": []},
        "print": {"private": [], "public": []},
    }


@pytest.fixture
def sample_setting_detail():
    """Sample setting detail from Bambu Cloud API."""
    return {
        "setting_id": "custom-pla-001",
        "name": "My Custom PLA @BBL X1C",
        "filament_id": "GFSL05",
        "base_id": "GFSL05_07",
    }
