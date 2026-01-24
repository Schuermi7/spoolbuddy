"""
Integration tests for Printer Discovery API.

Tests cover:
- Discovery status
- Start/stop discovery
- Get discovered printers
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from api.discovery import DiscoveredPrinter, DiscoveryState


class TestDiscoveryStatusAPI:
    """Tests for discovery status endpoint."""

    async def test_get_status_not_running(self, async_client):
        """Test status when discovery is not running."""
        mock_state = DiscoveryState(running=False, printers={}, task=None)

        with patch("api.discovery._state", mock_state):
            response = await async_client.get("/api/discovery/status")

        assert response.status_code == 200
        data = response.json()
        assert data["running"] is False

    async def test_get_status_running(self, async_client):
        """Test status when discovery is running."""
        mock_task = MagicMock()
        mock_state = DiscoveryState(running=True, printers={}, task=mock_task)

        with patch("api.discovery._state", mock_state):
            response = await async_client.get("/api/discovery/status")

        assert response.status_code == 200
        data = response.json()
        assert data["running"] is True


class TestDiscoveryStartAPI:
    """Tests for starting discovery."""

    async def test_start_discovery(self, async_client):
        """Test starting discovery sets running to True."""
        mock_state = DiscoveryState(running=False, printers={}, task=None)

        with (
            patch("api.discovery._state", mock_state),
            patch("api.discovery._discovery_task") as mock_task,
            patch("api.discovery.asyncio.create_task") as mock_create_task,
        ):
            mock_task.return_value = MagicMock()  # Prevent coroutine creation
            mock_create_task.return_value = MagicMock()
            response = await async_client.post("/api/discovery/start")

        assert response.status_code == 200
        data = response.json()
        assert data["running"] is True
        assert mock_state.running is True
        mock_create_task.assert_called_once()

    async def test_start_discovery_already_running(self, async_client):
        """Test starting discovery when already running returns running=True."""
        mock_task = MagicMock()
        mock_state = DiscoveryState(running=True, printers={}, task=mock_task)

        with patch("api.discovery._state", mock_state), patch("api.discovery.asyncio.create_task") as mock_create_task:
            response = await async_client.post("/api/discovery/start")

        assert response.status_code == 200
        data = response.json()
        assert data["running"] is True
        # Should not create a new task when already running
        mock_create_task.assert_not_called()

    async def test_start_discovery_clears_previous_printers(self, async_client):
        """Test starting discovery clears previously discovered printers."""
        existing_printers = {"OLD123": DiscoveredPrinter(serial="OLD123", ip_address="192.168.1.50")}
        mock_state = DiscoveryState(running=False, printers=existing_printers, task=None)

        with (
            patch("api.discovery._state", mock_state),
            patch("api.discovery._discovery_task") as mock_task,
            patch("api.discovery.asyncio.create_task") as mock_create_task,
        ):
            mock_task.return_value = MagicMock()  # Prevent coroutine creation
            mock_create_task.return_value = MagicMock()
            response = await async_client.post("/api/discovery/start")

        assert response.status_code == 200
        assert mock_state.printers == {}


class TestDiscoveryStopAPI:
    """Tests for stopping discovery."""

    async def test_stop_discovery(self, async_client):
        """Test stopping discovery sets running to False."""

        # Create a real asyncio task that we can cancel
        async def dummy_task():
            await asyncio.sleep(10)

        task = asyncio.create_task(dummy_task())
        mock_state = DiscoveryState(running=True, printers={}, task=task)

        with patch("api.discovery._state", mock_state):
            response = await async_client.post("/api/discovery/stop")

        assert response.status_code == 200
        data = response.json()
        assert data["running"] is False
        assert mock_state.running is False
        assert task.cancelled()

    async def test_stop_discovery_when_not_running(self, async_client):
        """Test stopping discovery when not running."""
        mock_state = DiscoveryState(running=False, printers={}, task=None)

        with patch("api.discovery._state", mock_state):
            response = await async_client.post("/api/discovery/stop")

        assert response.status_code == 200
        data = response.json()
        assert data["running"] is False


class TestDiscoveryPrintersAPI:
    """Tests for getting discovered printers."""

    async def test_get_printers_empty(self, async_client):
        """Test getting printers returns empty list initially."""
        mock_state = DiscoveryState(running=False, printers={}, task=None)

        with patch("api.discovery._state", mock_state):
            response = await async_client.get("/api/discovery/printers")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    async def test_get_printers_with_discovered(self, async_client):
        """Test getting printers returns discovered printers."""
        printers = {
            "ABC123456": DiscoveredPrinter(
                serial="ABC123456", name="My X1 Carbon", ip_address="192.168.1.100", model="X1-Carbon"
            ),
            "DEF789012": DiscoveredPrinter(serial="DEF789012", name="My P1S", ip_address="192.168.1.101", model="P1S"),
        }
        mock_state = DiscoveryState(running=True, printers=printers, task=MagicMock())

        with patch("api.discovery._state", mock_state):
            response = await async_client.get("/api/discovery/printers")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Check that both printers are in the response (order may vary)
        serials = {p["serial"] for p in data}
        assert serials == {"ABC123456", "DEF789012"}

        # Check a specific printer's data
        x1_printer = next(p for p in data if p["serial"] == "ABC123456")
        assert x1_printer["name"] == "My X1 Carbon"
        assert x1_printer["ip_address"] == "192.168.1.100"
        assert x1_printer["model"] == "X1-Carbon"

    async def test_get_printers_with_minimal_data(self, async_client):
        """Test getting printers with minimal printer data (only required fields)."""
        printers = {
            "MIN123": DiscoveredPrinter(serial="MIN123", ip_address="192.168.1.200"),
        }
        mock_state = DiscoveryState(running=False, printers=printers, task=None)

        with patch("api.discovery._state", mock_state):
            response = await async_client.get("/api/discovery/printers")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["serial"] == "MIN123"
        assert data[0]["ip_address"] == "192.168.1.200"
        assert data[0]["name"] is None
        assert data[0]["model"] is None
