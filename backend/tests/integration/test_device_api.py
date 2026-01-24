"""
Integration tests for ESP32 Device Connection API.

Tests cover:
- Connection status
- Device configuration
- Connect/disconnect
- Scale operations (tare, calibrate, reset)
- Device commands (reboot, update, factory reset)
- Recovery info
"""

from unittest.mock import AsyncMock, patch

import pytest
from api.device import DeviceInfo


class TestDeviceStatusAPI:
    """Tests for device connection status endpoint."""

    async def test_get_status_disconnected(self, async_client):
        """Test status when no device is connected."""
        with (
            patch("api.device._connected_device", None),
            patch("api.device._last_error", None),
            patch("api.device._reconnect_attempts", 0),
        ):
            response = await async_client.get("/api/device/status")

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False
        assert data["device"] is None

    async def test_get_status_connected(self, async_client):
        """Test status when device is connected."""
        mock_device = DeviceInfo(
            ip="192.168.1.100",
            hostname="spoolbuddy",
            firmware_version="1.0.0",
        )
        with (
            patch("api.device._connected_device", mock_device),
            patch("api.device._last_error", None),
            patch("api.device._reconnect_attempts", 0),
        ):
            response = await async_client.get("/api/device/status")

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["device"]["ip"] == "192.168.1.100"

    async def test_get_status_with_error(self, async_client):
        """Test status includes last error."""
        with (
            patch("api.device._connected_device", None),
            patch("api.device._last_error", "Connection timeout"),
            patch("api.device._reconnect_attempts", 3),
        ):
            response = await async_client.get("/api/device/status")

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False
        assert data["last_error"] == "Connection timeout"
        assert data["reconnect_attempts"] == 3


class TestDeviceConfigAPI:
    """Tests for device configuration endpoints."""

    async def test_get_config_empty(self, async_client):
        """Test getting config when none is saved."""
        with patch("api.device._device_config", None):
            response = await async_client.get("/api/device/config")

        assert response.status_code == 200
        assert response.json() is None

    async def test_save_config(self, async_client):
        """Test saving device configuration."""
        config = {"ip": "192.168.1.100", "port": 80, "name": "My SpoolBuddy"}

        response = await async_client.post("/api/device/config", json=config)

        assert response.status_code == 200
        data = response.json()
        assert data["ip"] == "192.168.1.100"
        assert data["port"] == 80
        assert data["name"] == "My SpoolBuddy"

    async def test_save_config_minimal(self, async_client):
        """Test saving config with only required fields."""
        config = {"ip": "192.168.1.100"}

        response = await async_client.post("/api/device/config", json=config)

        assert response.status_code == 200
        data = response.json()
        assert data["ip"] == "192.168.1.100"
        assert data["port"] == 80  # Default


class TestDeviceConnectAPI:
    """Tests for device connect/disconnect endpoints."""

    async def test_connect_no_config(self, async_client):
        """Test connect fails without configuration."""
        with patch("api.device._device_config", None):
            response = await async_client.post("/api/device/connect")

        assert response.status_code == 400
        assert "No device configuration" in response.json()["detail"]

    async def test_connect_success(self, async_client):
        """Test successful device connection."""
        from api.device import DeviceConfig

        mock_device_info = DeviceInfo(ip="192.168.1.100", hostname="spoolbuddy")
        mock_config = DeviceConfig(ip="192.168.1.100", port=80)

        with (
            patch("api.device._device_config", mock_config),
            patch("api.device._probe_device", AsyncMock(return_value=mock_device_info)),
        ):
            response = await async_client.post("/api/device/connect")

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True

    async def test_connect_with_config(self, async_client):
        """Test connect with provided configuration."""
        mock_device_info = DeviceInfo(ip="192.168.1.50")
        config = {"ip": "192.168.1.50", "port": 8080}

        with patch("api.device._probe_device", AsyncMock(return_value=mock_device_info)):
            response = await async_client.post("/api/device/connect", json=config)

        assert response.status_code == 200

    async def test_connect_device_not_responding(self, async_client):
        """Test connect when device doesn't respond."""
        from api.device import DeviceConfig

        mock_config = DeviceConfig(ip="192.168.1.100", port=80)

        with (
            patch("api.device._device_config", mock_config),
            patch("api.device._probe_device", AsyncMock(return_value=None)),
            patch("api.device._connected_device", None),
        ):
            response = await async_client.post("/api/device/connect")

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False

    async def test_disconnect(self, async_client):
        """Test device disconnect."""
        response = await async_client.post("/api/device/disconnect")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestDevicePingAPI:
    """Tests for device ping endpoint."""

    async def test_ping_reachable(self, async_client):
        """Test pinging a reachable device."""
        mock_device = DeviceInfo(ip="192.168.1.100")

        with patch("api.device._probe_device", AsyncMock(return_value=mock_device)):
            response = await async_client.post("/api/device/ping?ip=192.168.1.100")

        assert response.status_code == 200
        data = response.json()
        assert data["reachable"] is True

    async def test_ping_unreachable(self, async_client):
        """Test pinging an unreachable device."""
        with patch("api.device._probe_device", AsyncMock(return_value=None)):
            response = await async_client.post("/api/device/ping?ip=192.168.1.200")

        assert response.status_code == 200
        data = response.json()
        assert data["reachable"] is False
        assert data["device"] is None


class TestDeviceDiscoverAPI:
    """Tests for device discovery endpoint."""

    async def test_discover_finds_devices(self, async_client):
        """Test discovery finds devices."""
        mock_devices = [
            DeviceInfo(ip="192.168.1.100", hostname="spoolbuddy1"),
        ]

        with patch("api.device._discover_mdns", AsyncMock(return_value=mock_devices)):
            response = await async_client.post("/api/device/discover")

        assert response.status_code == 200
        data = response.json()
        assert "devices" in data
        assert len(data["devices"]) == 1
        assert "scan_duration_ms" in data

    async def test_discover_no_devices(self, async_client):
        """Test discovery with no devices found."""
        with (
            patch("api.device._discover_mdns", AsyncMock(return_value=[])),
            patch("api.device._discover_subnet", AsyncMock(return_value=[])),
        ):
            response = await async_client.post("/api/device/discover")

        assert response.status_code == 200
        data = response.json()
        assert data["devices"] == []

    async def test_discover_custom_timeout(self, async_client):
        """Test discovery with custom timeout."""
        with (
            patch("api.device._discover_mdns", AsyncMock(return_value=[])),
            patch("api.device._discover_subnet", AsyncMock(return_value=[])),
        ):
            response = await async_client.post("/api/device/discover?timeout_ms=5000")

        assert response.status_code == 200


class TestScaleAPI:
    """Tests for scale control endpoints."""

    async def test_tare_success(self, async_client):
        """Test tare command when device connected."""
        with patch("main.is_display_connected", return_value=True), patch("main.queue_display_command") as mock_queue:
            response = await async_client.post("/api/device/scale/tare")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_queue.assert_called_once_with("scale_tare")

    async def test_tare_no_device(self, async_client):
        """Test tare fails when no device connected."""
        with patch("main.is_display_connected", return_value=False):
            response = await async_client.post("/api/device/scale/tare")

        assert response.status_code == 400
        assert "No device connected" in response.json()["detail"]

    async def test_calibrate_success(self, async_client):
        """Test calibrate command with known weight."""
        with patch("main.is_display_connected", return_value=True), patch("main.queue_display_command") as mock_queue:
            response = await async_client.post("/api/device/scale/calibrate?known_weight=100.5")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_queue.assert_called_once_with("scale_calibrate:100.5")

    async def test_calibrate_no_device(self, async_client):
        """Test calibrate fails when no device connected."""
        with patch("main.is_display_connected", return_value=False):
            response = await async_client.post("/api/device/scale/calibrate?known_weight=100")

        assert response.status_code == 400

    async def test_reset_success(self, async_client):
        """Test scale reset command."""
        with patch("main.is_display_connected", return_value=True), patch("main.queue_display_command") as mock_queue:
            response = await async_client.post("/api/device/scale/reset")

        assert response.status_code == 200
        mock_queue.assert_called_once_with("scale_reset")

    async def test_reset_no_device(self, async_client):
        """Test scale reset fails when no device connected."""
        with patch("main.is_display_connected", return_value=False):
            response = await async_client.post("/api/device/scale/reset")

        assert response.status_code == 400


class TestDeviceCommandsAPI:
    """Tests for device command endpoints (reboot, update, factory reset)."""

    async def test_reboot_success(self, async_client):
        """Test reboot command."""
        with patch("main.is_display_connected", return_value=True), patch("main.queue_display_command") as mock_queue:
            response = await async_client.post("/api/device/reboot")

        assert response.status_code == 200
        mock_queue.assert_called_once_with("reboot")

    async def test_reboot_no_device(self, async_client):
        """Test reboot fails when no device connected."""
        with patch("main.is_display_connected", return_value=False):
            response = await async_client.post("/api/device/reboot")

        assert response.status_code == 400

    async def test_update_success(self, async_client):
        """Test update command."""
        with patch("main.is_display_connected", return_value=True), patch("main.queue_display_command") as mock_queue:
            response = await async_client.post("/api/device/update")

        assert response.status_code == 200
        mock_queue.assert_called_once_with("update")

    async def test_update_no_device(self, async_client):
        """Test update fails when no device connected."""
        with patch("main.is_display_connected", return_value=False):
            response = await async_client.post("/api/device/update")

        assert response.status_code == 400

    async def test_factory_reset_no_device(self, async_client):
        """Test factory reset fails when no device connected."""
        with patch("api.device._connected_device", None):
            response = await async_client.post("/api/device/factory-reset")

        assert response.status_code == 400


class TestRecoveryInfoAPI:
    """Tests for recovery info endpoint."""

    async def test_get_recovery_info(self, async_client):
        """Test getting USB recovery instructions."""
        response = await async_client.get("/api/device/recovery-info")

        assert response.status_code == 200
        data = response.json()
        assert "steps" in data
        assert "serial_commands" in data
        assert len(data["steps"]) > 0
        assert "flash" in data["serial_commands"]
