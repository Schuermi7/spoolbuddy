"""
Unit tests for MQTT client module.

Tests cover:
- PrinterConnection initialization
- AMS and tray parsing
- Dual-nozzle support
- Calibration profile handling
- Command generation
- Pending assignment lifecycle
"""

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from models import AmsTray, AmsUnit, PrinterState
from mqtt.client import (
    DISCONNECT_GRACE_PERIOD_SEC,
    STAGE_NAMES,
    Calibration,
    PendingAssignment,
    PrinterConnection,
    PrinterManager,
    get_stage_name,
)


class TestGetStageName:
    """Tests for get_stage_name function."""

    def test_known_stage(self):
        """Test known stage returns correct name."""
        assert get_stage_name(0) == "Printing"
        assert get_stage_name(1) == "Auto bed leveling"
        assert get_stage_name(7) == "Heating nozzle"
        assert get_stage_name(16) == "Paused by the user"

    def test_unknown_stage(self):
        """Test unknown stage returns formatted string."""
        assert get_stage_name(200) == "Unknown stage (200)"

    def test_idle_stage_x1(self):
        """Test X1 idle stage (-1) returns None."""
        assert get_stage_name(-1) is None

    def test_idle_stage_a1_p1(self):
        """Test A1/P1 idle stage (255) returns None."""
        assert get_stage_name(255) is None


class TestPrinterConnectionInit:
    """Tests for PrinterConnection initialization."""

    def test_creates_with_required_params(self):
        """Test PrinterConnection initializes with required parameters."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )

        assert conn.serial == "00M09A123456789"
        assert conn.ip_address == "192.168.1.100"
        assert conn.access_code == "12345678"
        assert conn.name is None
        assert conn._connected is False

    def test_creates_with_optional_name(self):
        """Test PrinterConnection initializes with optional name."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
            name="My Printer",
        )

        assert conn.name == "My Printer"

    def test_initial_state_empty(self):
        """Test initial printer state is empty."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )

        assert conn.state.gcode_state is None
        assert conn.state.ams_units == []
        assert conn.state.vt_tray is None


class TestPrinterConnectionConnectedProperty:
    """Tests for connected property with grace period."""

    def test_connected_when_true(self):
        """Test connected returns True when _connected is True."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )
        conn._connected = True

        assert conn.connected is True

    def test_disconnected_when_false_no_grace(self):
        """Test connected returns False when no grace period."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )
        conn._connected = False
        conn._disconnect_time = None

        assert conn.connected is False

    def test_connected_during_grace_period(self):
        """Test connected returns True during grace period."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )
        conn._connected = False
        conn._disconnect_time = time.time()  # Just disconnected

        assert conn.connected is True

    def test_disconnected_after_grace_period(self):
        """Test connected returns False after grace period expires."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )
        conn._connected = False
        conn._disconnect_time = time.time() - DISCONNECT_GRACE_PERIOD_SEC - 1

        assert conn.connected is False


class TestParseTray:
    """Tests for _parse_tray method."""

    def test_parses_filled_tray(self):
        """Test parsing a filled tray with all fields."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )

        tray_data = {
            "id": "0",
            "tray_type": "PLA",
            "tray_color": "FF0000FF",
            "tray_info_idx": "GFL05",
            "k": 0.025,
            "nozzle_temp_min": 190,
            "nozzle_temp_max": 230,
            "remain": 80,
        }

        tray = conn._parse_tray(tray_data, ams_id=0, tray_id=0)

        assert tray is not None
        assert tray.ams_id == 0
        assert tray.tray_id == 0
        assert tray.tray_type == "PLA"
        assert tray.tray_color == "FF0000FF"
        assert tray.tray_info_idx == "GFL05"
        assert tray.k_value == 0.025
        assert tray.nozzle_temp_min == 190
        assert tray.nozzle_temp_max == 230
        assert tray.remain == 80

    def test_parses_empty_tray(self):
        """Test parsing an empty tray."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )

        tray_data = {
            "id": "1",
            "tray_type": None,
            "tray_color": None,
        }

        tray = conn._parse_tray(tray_data, ams_id=0, tray_id=1)

        assert tray is not None
        assert tray.tray_type is None
        assert tray.tray_color is None
        assert tray.k_value is None

    def test_resolves_k_from_calibration(self):
        """Test k_value resolved from calibration index."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )
        # Add a calibration
        conn._calibrations[42] = Calibration(
            cali_idx=42,
            filament_id="GFL05",
            k_value=0.030,
            name="PLA Basic",
        )

        tray_data = {
            "id": "0",
            "tray_type": "PLA",
            "cali_idx": 42,
            # No direct k value
        }

        tray = conn._parse_tray(tray_data, ams_id=0, tray_id=0)

        assert tray.k_value == 0.030

    def test_handles_none_tray_data(self):
        """Test handling None tray data."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )

        tray = conn._parse_tray(None, ams_id=0, tray_id=0)
        assert tray is None

        tray = conn._parse_tray({}, ams_id=0, tray_id=0)
        assert tray is None


class TestParseAmsData:
    """Tests for _parse_ams_data method."""

    def test_parses_regular_ams(self, sample_mqtt_report):
        """Test parsing regular 4-slot AMS."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )
        conn._state = PrinterState()

        ams_data = sample_mqtt_report["print"]["ams"]
        conn._parse_ams_data(ams_data)

        assert len(conn._state.ams_units) == 1
        unit = conn._state.ams_units[0]
        assert unit.id == 0
        # humidity_raw (42) is preferred over humidity (35)
        assert unit.humidity == 42
        assert unit.temperature == 25.5
        # Fixture has 4 trays
        assert len(unit.trays) == 4

    def test_parses_tray_reading_bits(self):
        """Test parsing tray_reading_bits."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )
        conn._state = PrinterState()

        ams_data = {
            "ams": [
                {
                    "id": "0",
                    "humidity": 30,
                    "temp": "25.0",
                    "tray": [],
                }
            ],
            "tray_reading_bits": "0001",  # Tray 0 being read
        }

        conn._parse_ams_data(ams_data)
        assert conn._state.tray_reading_bits == 1

    def test_parses_ht_ams(self):
        """Test parsing single-slot HT AMS (id 128+)."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )
        conn._state = PrinterState()

        ams_data = {
            "ams": [
                {
                    "id": "128",
                    "humidity_raw": 40,
                    "temp": "28.0",
                    "tray": [
                        {
                            "id": "0",
                            "tray_type": "PLA-CF",
                            "tray_color": "808080FF",
                        }
                    ],
                }
            ],
        }

        conn._parse_ams_data(ams_data)

        assert len(conn._state.ams_units) == 1
        unit = conn._state.ams_units[0]
        assert unit.id == 128
        assert len(unit.trays) == 1
        assert unit.trays[0].tray_type == "PLA-CF"


class TestDualNozzleSupport:
    """Tests for dual-nozzle printer support."""

    def test_detects_dual_nozzle(self, sample_dual_nozzle_report):
        """Test detection of dual-nozzle printer from extruder_info."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )
        conn._state = PrinterState()
        conn._loop = None  # No event loop for test

        conn._handle_message(sample_dual_nozzle_report)

        assert conn._nozzle_count_detected is True
        assert conn._state.nozzle_count == 2

    def test_parses_tray_now_left_right(self, sample_dual_nozzle_report):
        """Test parsing tray_now_left/right from snow field."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )
        conn._state = PrinterState()
        conn._loop = None

        conn._handle_message(sample_dual_nozzle_report)

        # snow: 0x0001 for right (ams 0, slot 1), 0x0102 for left (ams 1, slot 2)
        assert conn._state.tray_now_right == 1  # ams 0 * 4 + slot 1
        assert conn._state.tray_now_left == 6  # ams 1 * 4 + slot 2

    def test_parses_active_extruder(self, sample_dual_nozzle_report):
        """Test parsing active_extruder from extruder state."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )
        conn._state = PrinterState()
        conn._loop = None

        conn._handle_message(sample_dual_nozzle_report)

        # extruder state = 0x10 means active_extruder = (0x10 >> 4) & 0xF = 1
        assert conn._state.active_extruder == 1

    def test_parses_nozzle_diameters(self, sample_dual_nozzle_report):
        """Test parsing nozzle diameters from extruder info."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )
        conn._state = PrinterState()
        conn._loop = None

        conn._handle_message(sample_dual_nozzle_report)

        assert conn._nozzle_diameters[0] == "0.4"
        assert conn._nozzle_diameters[1] == "0.6"


class TestCalibrationResponse:
    """Tests for handling calibration responses."""

    def test_parses_calibration_profiles(self, sample_calibration_profiles):
        """Test parsing calibration profiles from extrusion_cali_get response."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )

        print_data = {
            "command": "extrusion_cali_get",
            "nozzle_diameter": "0.4",
            "filaments": sample_calibration_profiles,
        }

        conn._handle_calibration_response(print_data)

        # Sample fixture has 3 calibration profiles
        assert len(conn._calibrations) == 3
        assert 42 in conn._calibrations
        cal = conn._calibrations[42]
        assert cal.k_value == 0.025
        assert cal.name == "Bambu PLA Basic"
        assert cal.filament_id == "GFSL05"

    def test_get_calibrations_returns_list(self, sample_calibration_profiles):
        """Test get_calibrations returns list of dicts."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )

        print_data = {
            "command": "extrusion_cali_get",
            "nozzle_diameter": "0.4",
            "filaments": sample_calibration_profiles,
        }
        conn._handle_calibration_response(print_data)

        cals = conn.get_calibrations()
        assert isinstance(cals, list)
        # Sample fixture has 3 calibration profiles
        assert len(cals) == 3
        assert all("cali_idx" in c for c in cals)
        assert all("k_value" in c for c in cals)


class TestSetFilamentCommand:
    """Tests for set_filament command generation."""

    def test_sends_correct_command(self):
        """Test set_filament sends correctly formatted MQTT message."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )
        conn._connected = True
        conn._client = MagicMock()
        conn._client.publish.return_value = MagicMock(rc=0)

        result = conn.set_filament(
            ams_id=0,
            tray_id=1,
            tray_info_idx="GFL05",
            setting_id="GFSL05_07",
            tray_type="PLA",
            tray_sub_brands="Bambu PLA Basic",
            tray_color="FF0000FF",
            nozzle_temp_min=190,
            nozzle_temp_max=230,
        )

        assert result is True
        conn._client.publish.assert_called_once()

        topic, payload = conn._client.publish.call_args[0]
        assert topic == "device/00M09A123456789/request"

        data = json.loads(payload)
        assert data["print"]["command"] == "ams_filament_setting"
        assert data["print"]["ams_id"] == 0
        assert data["print"]["tray_id"] == 1
        assert data["print"]["slot_id"] == 1
        assert data["print"]["tray_info_idx"] == "GFL05"
        assert data["print"]["setting_id"] == "GFSL05_07"
        assert data["print"]["tray_type"] == "PLA"
        assert data["print"]["tray_sub_brands"] == "Bambu PLA Basic"

    def test_fails_when_not_connected(self):
        """Test set_filament fails when not connected."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )
        conn._connected = False

        result = conn.set_filament(ams_id=0, tray_id=0)
        assert result is False


class TestSetCalibrationCommand:
    """Tests for set_calibration command generation."""

    def test_sends_extrusion_cali_sel(self):
        """Test set_calibration sends extrusion_cali_sel command."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )
        conn._connected = True
        conn._client = MagicMock()
        conn._client.publish.return_value = MagicMock(rc=0)

        result = conn.set_calibration(
            ams_id=0,
            tray_id=2,
            cali_idx=42,
            filament_id="GFL05",
            nozzle_diameter="0.4",
            setting_id="GFSL05_07",
        )

        assert result is True
        topic, payload = conn._client.publish.call_args[0]

        data = json.loads(payload)
        assert data["print"]["command"] == "extrusion_cali_sel"
        assert data["print"]["cali_idx"] == 42
        assert data["print"]["filament_id"] == "GFL05"
        assert data["print"]["nozzle_diameter"] == "0.4"
        assert data["print"]["ams_id"] == 0
        assert data["print"]["tray_id"] == 2
        assert data["print"]["slot_id"] == 2


class TestSetKValueCommand:
    """Tests for set_k_value command generation."""

    def test_sends_extrusion_cali_set(self):
        """Test set_k_value sends extrusion_cali_set command."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )
        conn._connected = True
        conn._client = MagicMock()
        conn._client.publish.return_value = MagicMock(rc=0)

        result = conn.set_k_value(
            tray_id=5,
            k_value=0.028,
            nozzle_diameter="0.4",
            nozzle_temp=210,
        )

        assert result is True
        topic, payload = conn._client.publish.call_args[0]

        data = json.loads(payload)
        assert data["print"]["command"] == "extrusion_cali_set"
        assert data["print"]["tray_id"] == 5
        assert data["print"]["k_value"] == 0.028
        assert data["print"]["nozzle_diameter"] == "0.4"
        assert data["print"]["nozzle_temp"] == 210


class TestPendingAssignment:
    """Tests for pending assignment lifecycle."""

    def test_stage_assignment(self):
        """Test staging a pending assignment."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )

        result = conn.stage_assignment(
            ams_id=0,
            tray_id=1,
            spool_id="spool-123",
            tray_info_idx="GFL05",
            setting_id="GFSL05_07",
            tray_type="PLA",
            tray_color="FF0000FF",
        )

        assert result is True
        assignment = conn.get_pending_assignment(0, 1)
        assert assignment is not None
        assert assignment.spool_id == "spool-123"
        assert assignment.tray_info_idx == "GFL05"

    def test_cancel_assignment(self):
        """Test cancelling a pending assignment."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )

        conn.stage_assignment(ams_id=0, tray_id=1, spool_id="spool-123")
        assert conn.get_pending_assignment(0, 1) is not None

        result = conn.cancel_assignment(0, 1)
        assert result is True
        assert conn.get_pending_assignment(0, 1) is None

    def test_cancel_nonexistent_assignment(self):
        """Test cancelling assignment that doesn't exist."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )

        result = conn.cancel_assignment(0, 1)
        assert result is False

    def test_get_all_pending_assignments(self):
        """Test getting all pending assignments."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )

        conn.stage_assignment(ams_id=0, tray_id=0, spool_id="spool-1")
        conn.stage_assignment(ams_id=0, tray_id=1, spool_id="spool-2")
        conn.stage_assignment(ams_id=1, tray_id=0, spool_id="spool-3")

        all_pending = conn.get_all_pending_assignments()
        assert len(all_pending) == 3
        assert (0, 0) in all_pending
        assert (0, 1) in all_pending
        assert (1, 0) in all_pending

    def test_execute_pending_assignment_on_insertion(self):
        """Test pending assignment executes when spool is inserted."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )
        conn._connected = True
        conn._client = MagicMock()
        conn._client.publish.return_value = MagicMock(rc=0)
        conn._state = PrinterState()
        conn._loop = None

        # Stage an assignment
        conn.stage_assignment(
            ams_id=0,
            tray_id=0,
            spool_id="spool-123",
            tray_info_idx="GFL05",
            tray_type="PLA",
            tray_color="FF0000FF",
        )

        # First update: empty slot
        ams_data = {
            "ams": [
                {
                    "id": "0",
                    "humidity": 30,
                    "temp": "25.0",
                    "tray": [
                        {
                            "id": "0",
                            "tray_type": None,  # Empty
                        }
                    ],
                }
            ],
        }
        conn._parse_ams_data(ams_data)

        # Assignment should still be pending
        assert conn.get_pending_assignment(0, 0) is not None

        # Second update: spool inserted
        ams_data = {
            "ams": [
                {
                    "id": "0",
                    "humidity": 30,
                    "temp": "25.0",
                    "tray": [
                        {
                            "id": "0",
                            "tray_type": "PLA",  # Now has filament
                        }
                    ],
                }
            ],
        }
        conn._parse_ams_data(ams_data)

        # Assignment should be executed and removed
        assert conn.get_pending_assignment(0, 0) is None
        # Should have called publish (set_filament + set_calibration)
        assert conn._client.publish.call_count >= 1


class TestResetSlot:
    """Tests for reset_slot command."""

    def test_sends_ams_get_rfid(self):
        """Test reset_slot sends ams_get_rfid command."""
        conn = PrinterConnection(
            serial="00M09A123456789",
            ip_address="192.168.1.100",
            access_code="12345678",
        )
        conn._connected = True
        conn._client = MagicMock()
        conn._client.publish.return_value = MagicMock(rc=0)

        result = conn.reset_slot(ams_id=0, tray_id=2)

        assert result is True
        topic, payload = conn._client.publish.call_args[0]

        data = json.loads(payload)
        assert data["print"]["command"] == "ams_get_rfid"
        assert data["print"]["ams_id"] == 0
        assert data["print"]["slot_id"] == 2


class TestPrinterManager:
    """Tests for PrinterManager."""

    def test_is_connected_false_when_not_connected(self):
        """Test is_connected returns False for unknown printer."""
        manager = PrinterManager()
        assert manager.is_connected("unknown") is False

    def test_get_state_none_when_not_connected(self):
        """Test get_state returns None for unknown printer."""
        manager = PrinterManager()
        assert manager.get_state("unknown") is None

    def test_set_callbacks(self):
        """Test setting callback functions."""
        manager = PrinterManager()

        state_cb = MagicMock()
        disconnect_cb = MagicMock()
        connect_cb = MagicMock()

        manager.set_state_callback(state_cb)
        manager.set_disconnect_callback(disconnect_cb)
        manager.set_connect_callback(connect_cb)

        assert manager._on_state_update == state_cb
        assert manager._on_disconnect == disconnect_cb
        assert manager._on_connect == connect_cb


class TestSafeConversions:
    """Tests for _safe_int and _safe_float methods."""

    def test_safe_int_with_int(self):
        """Test _safe_int with integer value."""
        assert PrinterConnection._safe_int(42) == 42

    def test_safe_int_with_string(self):
        """Test _safe_int with string value."""
        assert PrinterConnection._safe_int("42") == 42

    def test_safe_int_with_none(self):
        """Test _safe_int with None value."""
        assert PrinterConnection._safe_int(None) is None
        assert PrinterConnection._safe_int(None, 0) == 0

    def test_safe_int_with_invalid(self):
        """Test _safe_int with invalid value."""
        assert PrinterConnection._safe_int("not a number") is None
        assert PrinterConnection._safe_int("not a number", -1) == -1

    def test_safe_float_with_float(self):
        """Test _safe_float with float value."""
        assert PrinterConnection._safe_float(3.14) == 3.14

    def test_safe_float_with_string(self):
        """Test _safe_float with string value."""
        assert PrinterConnection._safe_float("3.14") == 3.14

    def test_safe_float_with_none(self):
        """Test _safe_float with None value."""
        assert PrinterConnection._safe_float(None) is None

    def test_safe_float_with_invalid(self):
        """Test _safe_float with invalid value."""
        assert PrinterConnection._safe_float("not a number") is None
