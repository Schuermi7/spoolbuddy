"""
Integration tests for Support API.

Tests cover:
- Debug logging state get/set
- Log retrieval and filtering
- Log clearing
- Support bundle generation
- System information
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestDebugLoggingAPI:
    """Tests for debug logging state endpoints."""

    async def test_get_debug_logging_disabled(self, async_client):
        """Test getting debug logging state when disabled."""
        with patch("api.support._get_debug_setting") as mock_get:
            mock_get.return_value = (False, None)

            response = await async_client.get("/api/support/debug-logging")

            assert response.status_code == 200
            data = response.json()
            assert data["enabled"] is False
            assert data["enabled_at"] is None
            assert data["duration_seconds"] is None

    async def test_get_debug_logging_enabled(self, async_client):
        """Test getting debug logging state when enabled."""
        with patch("api.support._get_debug_setting") as mock_get:
            mock_get.return_value = (True, "2024-01-15T10:30:00")

            response = await async_client.get("/api/support/debug-logging")

            assert response.status_code == 200
            data = response.json()
            assert data["enabled"] is True
            assert data["enabled_at"] == "2024-01-15T10:30:00"
            assert data["duration_seconds"] is not None

    async def test_enable_debug_logging(self, async_client):
        """Test enabling debug logging."""
        with (
            patch("api.support._set_debug_setting") as mock_set,
            patch("api.support._apply_log_level") as mock_apply,
        ):
            mock_set.return_value = "2024-01-15T10:30:00"

            response = await async_client.post("/api/support/debug-logging", json={"enabled": True})

            assert response.status_code == 200
            data = response.json()
            assert data["enabled"] is True
            assert data["enabled_at"] == "2024-01-15T10:30:00"
            assert data["duration_seconds"] == 0  # Just enabled

            mock_set.assert_called_once_with(True)
            mock_apply.assert_called_once()

    async def test_disable_debug_logging(self, async_client):
        """Test disabling debug logging."""
        with (
            patch("api.support._set_debug_setting") as mock_set,
            patch("api.support._apply_log_level") as mock_apply,
        ):
            mock_set.return_value = None

            response = await async_client.post("/api/support/debug-logging", json={"enabled": False})

            assert response.status_code == 200
            data = response.json()
            assert data["enabled"] is False
            assert data["enabled_at"] is None
            assert data["duration_seconds"] is None

            mock_set.assert_called_once_with(False)
            mock_apply.assert_called_once()


class TestLogsAPI:
    """Tests for log retrieval and management endpoints."""

    async def test_get_logs_empty(self, async_client):
        """Test getting logs when log file doesn't exist."""
        with patch("api.support.LOG_FILE", Path("/nonexistent/path/file.log")):
            response = await async_client.get("/api/support/logs")

            assert response.status_code == 200
            data = response.json()
            assert data["entries"] == []
            assert data["total_count"] == 0
            assert data["filtered_count"] == 0

    async def test_get_logs_with_entries(self, async_client):
        """Test getting logs with actual log entries."""
        log_content = """2024-01-15 10:30:00,123 INFO [main] Application started
2024-01-15 10:30:01,456 DEBUG [api.spools] Processing request
2024-01-15 10:30:02,789 ERROR [mqtt] Connection failed
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write(log_content)
            f.flush()
            temp_path = Path(f.name)

        try:
            with patch("api.support.LOG_FILE", temp_path):
                response = await async_client.get("/api/support/logs")

                assert response.status_code == 200
                data = response.json()
                assert data["total_count"] == 3
                assert data["filtered_count"] == 3
                assert len(data["entries"]) == 3
                # Entries are returned newest first
                assert data["entries"][0]["level"] == "ERROR"
                assert data["entries"][1]["level"] == "DEBUG"
                assert data["entries"][2]["level"] == "INFO"
        finally:
            temp_path.unlink()

    async def test_get_logs_with_level_filter(self, async_client):
        """Test getting logs filtered by level."""
        log_content = """2024-01-15 10:30:00,123 INFO [main] Application started
2024-01-15 10:30:01,456 DEBUG [api.spools] Processing request
2024-01-15 10:30:02,789 ERROR [mqtt] Connection failed
2024-01-15 10:30:03,012 ERROR [mqtt] Retry failed
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write(log_content)
            f.flush()
            temp_path = Path(f.name)

        try:
            with patch("api.support.LOG_FILE", temp_path):
                response = await async_client.get("/api/support/logs?level=ERROR")

                assert response.status_code == 200
                data = response.json()
                assert data["total_count"] == 4
                assert data["filtered_count"] == 2
                assert len(data["entries"]) == 2
                for entry in data["entries"]:
                    assert entry["level"] == "ERROR"
        finally:
            temp_path.unlink()

    async def test_get_logs_with_limit(self, async_client):
        """Test getting logs with limit parameter."""
        log_content = """2024-01-15 10:30:00,123 INFO [main] Entry 1
2024-01-15 10:30:01,456 INFO [main] Entry 2
2024-01-15 10:30:02,789 INFO [main] Entry 3
2024-01-15 10:30:03,012 INFO [main] Entry 4
2024-01-15 10:30:04,345 INFO [main] Entry 5
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write(log_content)
            f.flush()
            temp_path = Path(f.name)

        try:
            with patch("api.support.LOG_FILE", temp_path):
                response = await async_client.get("/api/support/logs?limit=2")

                assert response.status_code == 200
                data = response.json()
                assert data["total_count"] == 5
                assert data["filtered_count"] == 5
                assert len(data["entries"]) == 2
        finally:
            temp_path.unlink()

    async def test_get_logs_with_search(self, async_client):
        """Test getting logs with search filter."""
        log_content = """2024-01-15 10:30:00,123 INFO [main] Application started
2024-01-15 10:30:01,456 INFO [mqtt] MQTT connecting
2024-01-15 10:30:02,789 ERROR [mqtt] MQTT connection failed
2024-01-15 10:30:03,012 INFO [api.spools] Spool created
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write(log_content)
            f.flush()
            temp_path = Path(f.name)

        try:
            with patch("api.support.LOG_FILE", temp_path):
                response = await async_client.get("/api/support/logs?search=mqtt")

                assert response.status_code == 200
                data = response.json()
                assert data["total_count"] == 4
                assert data["filtered_count"] == 2
                assert len(data["entries"]) == 2
        finally:
            temp_path.unlink()

    async def test_clear_logs(self, async_client):
        """Test clearing log file."""
        log_content = "2024-01-15 10:30:00,123 INFO [main] Test log\n"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write(log_content)
            f.flush()
            temp_path = Path(f.name)

        try:
            with patch("api.support.LOG_FILE", temp_path):
                response = await async_client.delete("/api/support/logs")

                assert response.status_code == 200
                data = response.json()
                assert data["message"] == "Logs cleared"

                # Verify file is cleared
                assert temp_path.read_text() == ""
        finally:
            temp_path.unlink()

    async def test_clear_logs_nonexistent_file(self, async_client):
        """Test clearing logs when file doesn't exist."""
        with patch("api.support.LOG_FILE", Path("/nonexistent/path/file.log")):
            response = await async_client.delete("/api/support/logs")

            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "Logs cleared"


class TestSupportBundleAPI:
    """Tests for support bundle endpoint."""

    async def test_get_bundle_debug_not_enabled(self, async_client):
        """Test getting support bundle when debug logging is not enabled."""
        with patch("api.support._get_debug_setting") as mock_get:
            mock_get.return_value = (False, None)

            response = await async_client.get("/api/support/bundle")

            assert response.status_code == 400
            data = response.json()
            assert "Debug logging must be enabled" in data["detail"]

    async def test_get_bundle_success(self, async_client, test_db):
        """Test getting support bundle successfully."""
        log_content = "2024-01-15 10:30:00,123 INFO [main] Test log\n"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write(log_content)
            f.flush()
            temp_path = Path(f.name)

        try:
            mock_disk = MagicMock()
            mock_disk.total = 100 * 1024 * 1024 * 1024
            mock_disk.used = 50 * 1024 * 1024 * 1024
            mock_disk.free = 50 * 1024 * 1024 * 1024
            mock_disk.percent = 50.0

            mock_memory = MagicMock()
            mock_memory.total = 16 * 1024 * 1024 * 1024
            mock_memory.used = 8 * 1024 * 1024 * 1024
            mock_memory.available = 8 * 1024 * 1024 * 1024
            mock_memory.percent = 50.0

            with (
                patch("api.support._get_debug_setting") as mock_get,
                patch("api.support.LOG_FILE", temp_path),
                patch("api.support.psutil.disk_usage", return_value=mock_disk),
                patch("api.support.psutil.virtual_memory", return_value=mock_memory),
                patch("api.support.psutil.cpu_count", return_value=4),
                patch("api.support.get_db") as mock_db,
            ):
                mock_get.return_value = (True, "2024-01-15T10:30:00")
                mock_db.return_value = test_db

                response = await async_client.get("/api/support/bundle")

                assert response.status_code == 200
                assert response.headers["content-type"] == "application/zip"
                assert "attachment" in response.headers["content-disposition"]
                assert "spoolbuddy-support-" in response.headers["content-disposition"]
                assert ".zip" in response.headers["content-disposition"]
        finally:
            temp_path.unlink()


class TestSystemInfoAPI:
    """Tests for system information endpoint."""

    async def test_get_system_info(self, async_client, test_db):
        """Test getting system information."""
        mock_disk = MagicMock()
        mock_disk.total = 100 * 1024 * 1024 * 1024  # 100 GB
        mock_disk.used = 50 * 1024 * 1024 * 1024
        mock_disk.free = 50 * 1024 * 1024 * 1024
        mock_disk.percent = 50.0

        mock_memory = MagicMock()
        mock_memory.total = 16 * 1024 * 1024 * 1024  # 16 GB
        mock_memory.used = 8 * 1024 * 1024 * 1024
        mock_memory.available = 8 * 1024 * 1024 * 1024
        mock_memory.percent = 50.0

        mock_db_path = MagicMock()
        mock_db_path.exists.return_value = False

        with (
            patch("api.support.psutil.disk_usage", return_value=mock_disk),
            patch("api.support.psutil.virtual_memory", return_value=mock_memory),
            patch("api.support.psutil.cpu_count", return_value=4),
            patch("api.support.psutil.cpu_percent", return_value=25.0),
            patch("api.support.psutil.boot_time", return_value=1705300000.0),
            patch("api.support.get_db") as mock_get_db,
            patch("api.support.settings") as mock_settings,
        ):
            mock_get_db.return_value = test_db
            mock_settings.database_path = mock_db_path

            response = await async_client.get("/api/support/system-info")

            assert response.status_code == 200
            data = response.json()

            # Application info
            assert "version" in data
            assert "uptime" in data
            assert "uptime_seconds" in data
            assert "hostname" in data

            # Database stats
            assert "spool_count" in data
            assert "printer_count" in data
            assert "connected_printers" in data

            # Storage
            assert "database_size" in data
            assert "disk_total" in data
            assert "disk_used" in data
            assert "disk_free" in data
            assert "disk_percent" in data

            # System
            assert "platform" in data
            assert "platform_release" in data
            assert "python_version" in data
            assert "boot_time" in data

            # Memory
            assert "memory_total" in data
            assert "memory_used" in data
            assert "memory_available" in data
            assert data["memory_percent"] == 50.0

            # CPU
            assert data["cpu_count"] == 4
            assert data["cpu_percent"] == 25.0

    async def test_get_system_info_with_spools_and_printers(
        self, async_client, test_db, spool_factory, printer_factory
    ):
        """Test system info includes correct spool and printer counts."""
        # Create test data
        await spool_factory(material="PLA")
        await spool_factory(material="PETG")
        await printer_factory(serial="00M09A000000001")

        mock_disk = MagicMock()
        mock_disk.total = 100 * 1024 * 1024 * 1024
        mock_disk.used = 50 * 1024 * 1024 * 1024
        mock_disk.free = 50 * 1024 * 1024 * 1024
        mock_disk.percent = 50.0

        mock_memory = MagicMock()
        mock_memory.total = 16 * 1024 * 1024 * 1024
        mock_memory.used = 8 * 1024 * 1024 * 1024
        mock_memory.available = 8 * 1024 * 1024 * 1024
        mock_memory.percent = 50.0

        mock_db_path = MagicMock()
        mock_db_path.exists.return_value = False

        with (
            patch("api.support.psutil.disk_usage", return_value=mock_disk),
            patch("api.support.psutil.virtual_memory", return_value=mock_memory),
            patch("api.support.psutil.cpu_count", return_value=4),
            patch("api.support.psutil.cpu_percent", return_value=25.0),
            patch("api.support.psutil.boot_time", return_value=1705300000.0),
            patch("api.support.get_db") as mock_get_db,
            patch("api.support.settings") as mock_settings,
        ):
            mock_get_db.return_value = test_db
            mock_settings.database_path = mock_db_path

            response = await async_client.get("/api/support/system-info")

            assert response.status_code == 200
            data = response.json()

            assert data["spool_count"] == 2
            assert data["printer_count"] == 1
            assert data["connected_printers"] == 0
