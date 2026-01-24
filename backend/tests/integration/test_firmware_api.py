"""
Integration tests for ESP32 Firmware OTA Update API.

Tests cover:
- Listing firmware versions
- Getting latest firmware
- Checking for updates (GitHub API)
- Downloading firmware files
- Uploading firmware binaries
- Deleting firmware versions
"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestFirmwareVersionAPI:
    """Tests for firmware version listing endpoints."""

    async def test_list_versions_empty(self, async_client):
        """Test listing firmware versions when none exist."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            with patch("api.firmware.FIRMWARE_DIR", tmp_path):
                response = await async_client.get("/api/firmware/version")

        assert response.status_code == 200
        assert response.json() == []

    async def test_list_versions_with_firmware(self, async_client):
        """Test listing firmware versions with files present."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # Create test firmware files
            (tmp_path / "spoolbuddy-1.0.0.bin").write_bytes(b"\x00" * 100)
            (tmp_path / "spoolbuddy-1.1.0.bin").write_bytes(b"\x00" * 200)
            (tmp_path / "spoolbuddy-0.9.0.bin").write_bytes(b"\x00" * 50)

            with patch("api.firmware.FIRMWARE_DIR", tmp_path):
                response = await async_client.get("/api/firmware/version")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        # Should be sorted descending by version
        assert data[0]["version"] == "1.1.0"
        assert data[1]["version"] == "1.0.0"
        assert data[2]["version"] == "0.9.0"

    async def test_list_versions_with_prerelease(self, async_client):
        """Test listing firmware versions with pre-release versions."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # Create test firmware files with pre-release versions
            (tmp_path / "spoolbuddy-1.0.0.bin").write_bytes(b"\x00" * 100)
            (tmp_path / "spoolbuddy-1.0.0b1.bin").write_bytes(b"\x00" * 100)
            (tmp_path / "spoolbuddy-1.0.0a1.bin").write_bytes(b"\x00" * 100)

            with patch("api.firmware.FIRMWARE_DIR", tmp_path):
                response = await async_client.get("/api/firmware/version")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        # Release > rc > beta > alpha
        assert data[0]["version"] == "1.0.0"
        assert data[1]["version"] == "1.0.0b1"
        assert data[2]["version"] == "1.0.0a1"


class TestLatestFirmwareAPI:
    """Tests for getting latest firmware version."""

    async def test_latest_no_firmware(self, async_client):
        """Test getting latest firmware when none exist returns 404."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            with patch("api.firmware.FIRMWARE_DIR", tmp_path):
                response = await async_client.get("/api/firmware/latest")

        assert response.status_code == 404
        assert "No firmware available" in response.json()["detail"]

    async def test_latest_with_firmware(self, async_client):
        """Test getting latest firmware version."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "spoolbuddy-1.0.0.bin").write_bytes(b"\x00" * 100)
            (tmp_path / "spoolbuddy-2.0.0.bin").write_bytes(b"\x00" * 200)

            with patch("api.firmware.FIRMWARE_DIR", tmp_path):
                response = await async_client.get("/api/firmware/latest")

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "2.0.0"
        assert data["filename"] == "spoolbuddy-2.0.0.bin"
        assert data["size"] == 200


class TestFirmwareCheckAPI:
    """Tests for firmware update checking endpoint."""

    async def test_check_mocked_github_response(self, async_client):
        """Test checking for updates with mocked GitHub response."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = [
                {
                    "tag_name": "v2.0.0",
                    "body": "New release notes",
                    "assets": [
                        {
                            "name": "spoolbuddy-2.0.0.bin",
                            "browser_download_url": "https://github.com/test/releases/download/v2.0.0/spoolbuddy-2.0.0.bin",
                        }
                    ],
                }
            ]

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)

            with (
                patch("api.firmware.FIRMWARE_DIR", tmp_path),
                patch("api.firmware._firmware_cache", None),
                patch("api.firmware._firmware_cache_time", None),
                patch("httpx.AsyncClient") as mock_httpx,
                patch("main.get_display_firmware_version", return_value="1.0.0"),
            ):
                mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_httpx.return_value.__aexit__ = AsyncMock()

                response = await async_client.get("/api/firmware/check?current_version=1.0.0")

        assert response.status_code == 200
        data = response.json()
        assert data["current_version"] == "1.0.0"
        assert data["latest_version"] == "2.0.0"
        assert data["update_available"] is True
        assert "2.0.0" in data["download_url"]

    async def test_check_no_update_available(self, async_client):
        """Test check when current version is latest."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "spoolbuddy-1.0.0.bin").write_bytes(b"\x00" * 100)

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = [
                {
                    "tag_name": "v1.0.0",
                    "body": "Current release",
                    "assets": [
                        {
                            "name": "spoolbuddy-1.0.0.bin",
                            "browser_download_url": "https://github.com/test/releases/download/v1.0.0/spoolbuddy-1.0.0.bin",
                        }
                    ],
                }
            ]

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)

            with (
                patch("api.firmware.FIRMWARE_DIR", tmp_path),
                patch("api.firmware._firmware_cache", None),
                patch("api.firmware._firmware_cache_time", None),
                patch("httpx.AsyncClient") as mock_httpx,
                patch("main.get_display_firmware_version", return_value="1.0.0"),
            ):
                mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_httpx.return_value.__aexit__ = AsyncMock()

                response = await async_client.get("/api/firmware/check?current_version=1.0.0")

        assert response.status_code == 200
        data = response.json()
        assert data["update_available"] is False

    async def test_check_uses_cache(self, async_client):
        """Test that firmware check uses cached data."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            cached_data = {
                "version": "2.5.0",
                "filename": "spoolbuddy-2.5.0.bin",
                "url": "https://github.com/cached/url",
                "notes": "Cached notes",
            }

            with (
                patch("api.firmware.FIRMWARE_DIR", tmp_path),
                patch("api.firmware._firmware_cache", cached_data),
                patch("api.firmware._firmware_cache_time", datetime.now()),
                patch("main.get_display_firmware_version", return_value="1.0.0"),
            ):
                response = await async_client.get("/api/firmware/check?current_version=1.0.0")

        assert response.status_code == 200
        data = response.json()
        assert data["latest_version"] == "2.5.0"
        assert data["update_available"] is True

    async def test_check_expired_cache(self, async_client):
        """Test that expired cache triggers new GitHub fetch."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            expired_cache = {
                "version": "1.0.0",
                "filename": "spoolbuddy-1.0.0.bin",
                "url": "https://github.com/old/url",
            }

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = [
                {
                    "tag_name": "v3.0.0",
                    "body": "New release",
                    "assets": [
                        {
                            "name": "spoolbuddy-3.0.0.bin",
                            "browser_download_url": "https://github.com/new/url",
                        }
                    ],
                }
            ]

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)

            expired_time = datetime.now() - timedelta(minutes=10)

            with (
                patch("api.firmware.FIRMWARE_DIR", tmp_path),
                patch("api.firmware._firmware_cache", expired_cache),
                patch("api.firmware._firmware_cache_time", expired_time),
                patch("httpx.AsyncClient") as mock_httpx,
                patch("main.get_display_firmware_version", return_value="1.0.0"),
            ):
                mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                mock_httpx.return_value.__aexit__ = AsyncMock()

                response = await async_client.get("/api/firmware/check?current_version=1.0.0")

        assert response.status_code == 200
        data = response.json()
        assert data["latest_version"] == "3.0.0"


class TestFirmwareDownloadAPI:
    """Tests for firmware download endpoint."""

    async def test_download_invalid_filename_no_bin(self, async_client):
        """Test downloading with invalid filename (no .bin) returns 400."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            with patch("api.firmware.FIRMWARE_DIR", tmp_path):
                response = await async_client.get("/api/firmware/download/firmware.txt")

        assert response.status_code == 400
        assert "Invalid filename" in response.json()["detail"]

    async def test_download_invalid_filename_backslash(self, async_client):
        """Test downloading with backslash path traversal returns 400."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            with patch("api.firmware.FIRMWARE_DIR", tmp_path):
                response = await async_client.get("/api/firmware/download/..\\..\\secret.bin")

        assert response.status_code == 400
        assert "Invalid filename" in response.json()["detail"]

    async def test_download_nonexistent_file(self, async_client):
        """Test downloading non-existent firmware returns 404."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            with patch("api.firmware.FIRMWARE_DIR", tmp_path):
                response = await async_client.get("/api/firmware/download/spoolbuddy-9.9.9.bin")

        assert response.status_code == 404
        assert "Firmware not found" in response.json()["detail"]

    async def test_download_success(self, async_client):
        """Test successful firmware download."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            firmware_content = b"\xe9" + b"\x00" * 255  # ESP32 magic byte + padding
            (tmp_path / "spoolbuddy-1.0.0.bin").write_bytes(firmware_content)

            with patch("api.firmware.FIRMWARE_DIR", tmp_path):
                response = await async_client.get("/api/firmware/download/spoolbuddy-1.0.0.bin")

        assert response.status_code == 200
        assert response.content == firmware_content
        assert response.headers["content-type"] == "application/octet-stream"


class TestFirmwareOtaAPI:
    """Tests for ESP32 OTA endpoint."""

    async def test_ota_no_firmware(self, async_client):
        """Test OTA endpoint when no firmware available."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            with patch("api.firmware.FIRMWARE_DIR", tmp_path):
                response = await async_client.get("/api/firmware/ota")

        assert response.status_code == 404
        assert "No firmware available" in response.json()["detail"]

    async def test_ota_specific_version_not_found(self, async_client):
        """Test OTA endpoint with non-existent version."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "spoolbuddy-1.0.0.bin").write_bytes(b"\x00" * 100)

            with patch("api.firmware.FIRMWARE_DIR", tmp_path):
                response = await async_client.get("/api/firmware/ota?version=9.9.9")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    async def test_ota_success(self, async_client):
        """Test successful OTA firmware download."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            firmware_content = b"\xe9" + b"\x00" * 255
            (tmp_path / "spoolbuddy-1.0.0.bin").write_bytes(firmware_content)

            with patch("api.firmware.FIRMWARE_DIR", tmp_path):
                response = await async_client.get("/api/firmware/ota")

        assert response.status_code == 200
        assert response.content == firmware_content
        assert response.headers["x-firmware-version"] == "1.0.0"

    async def test_ota_specific_version(self, async_client):
        """Test OTA endpoint with specific version."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "spoolbuddy-1.0.0.bin").write_bytes(b"\x00" * 100)
            (tmp_path / "spoolbuddy-2.0.0.bin").write_bytes(b"\x00" * 200)

            with patch("api.firmware.FIRMWARE_DIR", tmp_path):
                response = await async_client.get("/api/firmware/ota?version=1.0.0")

        assert response.status_code == 200
        assert response.headers["x-firmware-version"] == "1.0.0"


class TestFirmwareUploadAPI:
    """Tests for firmware upload endpoint."""

    async def test_upload_invalid_file_type(self, async_client):
        """Test uploading non-.bin file returns 400."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            with patch("api.firmware.FIRMWARE_DIR", tmp_path):
                response = await async_client.post(
                    "/api/firmware/upload",
                    files={"file": ("firmware.txt", b"not a binary", "text/plain")},
                )

        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]

    async def test_upload_invalid_esp32_firmware(self, async_client):
        """Test uploading invalid ESP32 binary returns 400."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # File too small to be valid firmware
            with patch("api.firmware.FIRMWARE_DIR", tmp_path):
                response = await async_client.post(
                    "/api/firmware/upload",
                    files={"file": ("spoolbuddy-1.0.0.bin", b"\x00" * 100, "application/octet-stream")},
                )

        assert response.status_code == 400
        assert "Invalid firmware" in response.json()["detail"]

    async def test_upload_wrong_magic_byte(self, async_client):
        """Test uploading binary with wrong magic byte returns 400."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # Large enough but wrong magic byte (0x00 instead of 0xE9)
            invalid_firmware = b"\x00" * 1024
            with patch("api.firmware.FIRMWARE_DIR", tmp_path):
                response = await async_client.post(
                    "/api/firmware/upload",
                    files={"file": ("spoolbuddy-1.0.0.bin", invalid_firmware, "application/octet-stream")},
                )

        assert response.status_code == 400
        assert "Invalid firmware" in response.json()["detail"]
        assert "magic byte" in response.json()["detail"].lower()

    async def test_upload_success_with_version_in_filename(self, async_client):
        """Test successful upload extracting version from filename."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Create valid ESP32 firmware with magic byte but no app descriptor
            # Magic byte 0xE9 + minimal padding
            valid_firmware = b"\xe9" + b"\x00" * 1023

            with patch("api.firmware.FIRMWARE_DIR", tmp_path):
                response = await async_client.post(
                    "/api/firmware/upload",
                    files={"file": ("spoolbuddy-1.2.3.bin", valid_firmware, "application/octet-stream")},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["version"] == "1.2.3"
        assert data["filename"] == "spoolbuddy-1.2.3.bin"

    async def test_upload_with_explicit_version(self, async_client):
        """Test upload with explicit version parameter."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            valid_firmware = b"\xe9" + b"\x00" * 1023

            with patch("api.firmware.FIRMWARE_DIR", tmp_path):
                response = await async_client.post(
                    "/api/firmware/upload",
                    files={"file": ("firmware.bin", valid_firmware, "application/octet-stream")},
                    data={"version": "v3.0.0"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["version"] == "3.0.0"  # v prefix should be stripped

    async def test_upload_no_version_fails(self, async_client):
        """Test upload without version information fails."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Valid ESP32 magic but no app descriptor and no version in filename
            valid_firmware = b"\xe9" + b"\x00" * 1023

            with patch("api.firmware.FIRMWARE_DIR", tmp_path):
                response = await async_client.post(
                    "/api/firmware/upload",
                    files={"file": ("firmware.bin", valid_firmware, "application/octet-stream")},
                )

        assert response.status_code == 400
        assert "Could not determine firmware version" in response.json()["detail"]


class TestFirmwareDeleteAPI:
    """Tests for firmware deletion endpoint."""

    async def test_delete_nonexistent_version(self, async_client):
        """Test deleting non-existent firmware version returns 404."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            with patch("api.firmware.FIRMWARE_DIR", tmp_path):
                response = await async_client.delete("/api/firmware/9.9.9")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    async def test_delete_success(self, async_client):
        """Test successful firmware deletion."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            firmware_file = tmp_path / "spoolbuddy-1.0.0.bin"
            firmware_file.write_bytes(b"\x00" * 100)

            with patch("api.firmware.FIRMWARE_DIR", tmp_path):
                response = await async_client.delete("/api/firmware/1.0.0")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "deleted" in data["message"].lower()
        assert not firmware_file.exists()

    async def test_delete_with_v_prefix(self, async_client):
        """Test deletion with v prefix in version."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            firmware_file = tmp_path / "spoolbuddy-2.0.0.bin"
            firmware_file.write_bytes(b"\x00" * 100)

            with patch("api.firmware.FIRMWARE_DIR", tmp_path):
                response = await async_client.delete("/api/firmware/v2.0.0")

        assert response.status_code == 200
        assert not firmware_file.exists()


class TestVersionParsing:
    """Tests for version parsing and comparison logic."""

    def test_parse_version_simple(self):
        """Test parsing simple semver versions."""
        from api.firmware import _parse_version

        assert _parse_version("1.0.0") == (1, 0, 0, 3, 0)
        assert _parse_version("0.1.0") == (0, 1, 0, 3, 0)
        assert _parse_version("10.20.30") == (10, 20, 30, 3, 0)

    def test_parse_version_prerelease(self):
        """Test parsing pre-release versions."""
        from api.firmware import _parse_version

        assert _parse_version("1.0.0a1") == (1, 0, 0, 0, 1)
        assert _parse_version("1.0.0b2") == (1, 0, 0, 1, 2)
        assert _parse_version("1.0.0rc1") == (1, 0, 0, 2, 1)

    def test_parse_version_ordering(self):
        """Test that pre-release versions sort correctly."""
        from api.firmware import _parse_version

        # alpha < beta < rc < release
        assert _parse_version("1.0.0a1") < _parse_version("1.0.0b1")
        assert _parse_version("1.0.0b1") < _parse_version("1.0.0rc1")
        assert _parse_version("1.0.0rc1") < _parse_version("1.0.0")

    def test_parse_version_invalid(self):
        """Test parsing invalid version strings."""
        from api.firmware import _parse_version

        assert _parse_version("invalid") is None
        assert _parse_version("1.0") is None
        assert _parse_version("") is None

    def test_compare_versions(self):
        """Test version comparison function."""
        from api.firmware import _compare_versions

        assert _compare_versions("1.0.0", "2.0.0") is True
        assert _compare_versions("2.0.0", "1.0.0") is False
        assert _compare_versions("1.0.0", "1.0.0") is False
        assert _compare_versions("1.0.0b1", "1.0.0") is True


class TestFirmwareValidation:
    """Tests for ESP32 firmware validation."""

    def test_validate_too_small(self):
        """Test validation rejects files that are too small."""
        from api.firmware import FirmwareValidationError, _validate_esp32_firmware

        with pytest.raises(FirmwareValidationError, match="too small"):
            _validate_esp32_firmware(b"\x00" * 100)

    def test_validate_wrong_magic(self):
        """Test validation rejects wrong magic byte."""
        from api.firmware import FirmwareValidationError, _validate_esp32_firmware

        with pytest.raises(FirmwareValidationError, match="magic byte"):
            _validate_esp32_firmware(b"\x00" * 1024)

    def test_validate_valid_no_descriptor(self):
        """Test validation passes for valid firmware without app descriptor."""
        from api.firmware import _validate_esp32_firmware

        # ESP32 magic byte + padding
        firmware = b"\xe9" + b"\x00" * 1023
        result = _validate_esp32_firmware(firmware)

        assert result["valid"] is True
        assert result["has_descriptor"] is False
