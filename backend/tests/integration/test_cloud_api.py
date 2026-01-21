"""
Integration tests for Bambu Cloud API endpoints.

Tests cover:
- Authentication status
- Login flow
- Verification code
- Token management
- Slicer settings retrieval
- Setting details
- Logout
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta


class TestCloudStatusAPI:
    """Tests for cloud authentication status endpoint."""

    async def test_status_unauthenticated(self, async_client, test_db):
        """Test status returns is_authenticated: false when not logged in."""
        # Ensure no stored token
        await test_db.delete_setting("cloud_access_token")
        await test_db.delete_setting("cloud_email")

        response = await async_client.get("/api/cloud/status")

        assert response.status_code == 200
        data = response.json()
        assert data["is_authenticated"] is False
        assert data["email"] is None

    async def test_status_authenticated(self, async_client, test_db):
        """Test status returns is_authenticated: true with valid token."""
        # Store mock token
        await test_db.set_setting("cloud_access_token", "test-token")
        await test_db.set_setting("cloud_email", "test@example.com")

        # Patch where the function is used (api.cloud), not where it's defined
        with patch('api.cloud.get_cloud_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.is_authenticated = True
            mock_get_service.return_value = mock_service

            response = await async_client.get("/api/cloud/status")

        assert response.status_code == 200
        data = response.json()
        assert data["is_authenticated"] is True
        assert data["email"] == "test@example.com"


class TestCloudLoginAPI:
    """Tests for cloud login endpoint."""

    async def test_login_needs_verification(self, async_client):
        """Test login returns needs_verification when 2FA required."""
        with patch('api.cloud.get_cloud_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.login_request = AsyncMock(return_value={
                "success": False,
                "needs_verification": True,
                "message": "Verification code sent"
            })
            mock_get_service.return_value = mock_service

            response = await async_client.post(
                "/api/cloud/login",
                json={"email": "test@example.com", "password": "password123"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["needs_verification"] is True

    async def test_login_direct_success(self, async_client, test_db):
        """Test login succeeds directly without verification."""
        with patch('api.cloud.get_cloud_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.access_token = "new-access-token"
            mock_service.login_request = AsyncMock(return_value={
                "success": True,
                "needs_verification": False,
                "message": "Login successful"
            })
            mock_get_service.return_value = mock_service

            response = await async_client.post(
                "/api/cloud/login",
                json={"email": "test@example.com", "password": "password123"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["needs_verification"] is False

    async def test_login_failure(self, async_client):
        """Test login failure returns error message."""
        with patch('api.cloud.get_cloud_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.login_request = AsyncMock(return_value={
                "success": False,
                "needs_verification": False,
                "message": "Invalid credentials"
            })
            mock_get_service.return_value = mock_service

            response = await async_client.post(
                "/api/cloud/login",
                json={"email": "test@example.com", "password": "wrong"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Invalid credentials" in data["message"]

    async def test_login_auth_error(self, async_client):
        """Test login raises 401 on auth error."""
        from services.bambu_cloud import BambuCloudAuthError

        with patch('api.cloud.get_cloud_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.login_request = AsyncMock(
                side_effect=BambuCloudAuthError("Auth failed")
            )
            mock_get_service.return_value = mock_service

            response = await async_client.post(
                "/api/cloud/login",
                json={"email": "test@example.com", "password": "password"}
            )

        assert response.status_code == 401


class TestCloudVerifyAPI:
    """Tests for cloud verification endpoint."""

    async def test_verify_success(self, async_client, test_db):
        """Test verification completes login successfully."""
        with patch('api.cloud.get_cloud_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.access_token = "verified-token"
            mock_service.verify_code = AsyncMock(return_value={
                "success": True,
                "message": "Login successful"
            })
            mock_get_service.return_value = mock_service

            response = await async_client.post(
                "/api/cloud/verify",
                json={"email": "test@example.com", "code": "123456"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    async def test_verify_failure(self, async_client):
        """Test verification failure with invalid code."""
        with patch('api.cloud.get_cloud_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.verify_code = AsyncMock(return_value={
                "success": False,
                "message": "Invalid code"
            })
            mock_get_service.return_value = mock_service

            response = await async_client.post(
                "/api/cloud/verify",
                json={"email": "test@example.com", "code": "000000"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False


class TestCloudTokenAPI:
    """Tests for direct token setting endpoint."""

    async def test_set_token_valid(self, async_client, test_db):
        """Test setting valid token directly."""
        with patch('api.cloud.get_cloud_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_slicer_settings = AsyncMock(return_value={"filament": []})
            mock_get_service.return_value = mock_service

            response = await async_client.post(
                "/api/cloud/token",
                json={"access_token": "valid-token"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["is_authenticated"] is True

    async def test_set_token_invalid(self, async_client):
        """Test setting invalid token fails."""
        from services.bambu_cloud import BambuCloudError

        with patch('api.cloud.get_cloud_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_slicer_settings = AsyncMock(
                side_effect=BambuCloudError("Invalid token")
            )
            mock_get_service.return_value = mock_service

            response = await async_client.post(
                "/api/cloud/token",
                json={"access_token": "invalid-token"}
            )

        assert response.status_code == 401
        assert "Invalid token" in response.json()["detail"]


class TestCloudLogoutAPI:
    """Tests for cloud logout endpoint."""

    async def test_logout_clears_credentials(self, async_client, test_db):
        """Test logout clears stored credentials."""
        # Store credentials first
        await test_db.set_setting("cloud_access_token", "token")
        await test_db.set_setting("cloud_email", "test@example.com")

        with patch('api.cloud.get_cloud_service') as mock_get_service:
            mock_service = MagicMock()
            mock_get_service.return_value = mock_service

            response = await async_client.post("/api/cloud/logout")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify credentials cleared
        token = await test_db.get_setting("cloud_access_token")
        assert token is None


class TestCloudSettingsAPI:
    """Tests for slicer settings retrieval endpoints."""

    async def test_get_settings_authenticated(self, async_client, test_db, sample_slicer_settings):
        """Test getting slicer settings when authenticated."""
        await test_db.set_setting("cloud_access_token", "valid-token")

        with patch('api.cloud.get_cloud_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.is_authenticated = True
            mock_service.get_slicer_settings = AsyncMock(return_value=sample_slicer_settings)
            mock_get_service.return_value = mock_service

            response = await async_client.get("/api/cloud/settings")

        assert response.status_code == 200
        data = response.json()
        assert "filament" in data

    async def test_get_settings_unauthenticated(self, async_client, test_db):
        """Test getting settings without authentication returns 401."""
        # Ensure no token stored
        await test_db.delete_setting("cloud_access_token")

        response = await async_client.get("/api/cloud/settings")

        assert response.status_code == 401

    async def test_get_settings_expired_token(self, async_client, test_db):
        """Test getting settings with expired token clears credentials."""
        await test_db.set_setting("cloud_access_token", "expired-token")

        with patch('api.cloud.get_cloud_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.is_authenticated = False  # Expired
            mock_get_service.return_value = mock_service

            response = await async_client.get("/api/cloud/settings")

        assert response.status_code == 401

    async def test_get_settings_with_version(self, async_client, test_db):
        """Test getting settings with custom version parameter."""
        await test_db.set_setting("cloud_access_token", "valid-token")

        with patch('api.cloud.get_cloud_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.is_authenticated = True
            mock_service.get_slicer_settings = AsyncMock(return_value={"filament": {"public": [], "private": []}})
            mock_get_service.return_value = mock_service

            response = await async_client.get("/api/cloud/settings?version=01.00.00.00")

        assert response.status_code == 200
        mock_service.get_slicer_settings.assert_called_once_with("01.00.00.00")


class TestCloudSettingDetailAPI:
    """Tests for setting detail endpoint."""

    async def test_get_setting_detail(self, async_client, test_db, sample_setting_detail):
        """Test getting specific setting detail."""
        await test_db.set_setting("cloud_access_token", "valid-token")

        with patch('api.cloud.get_cloud_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.is_authenticated = True
            mock_service.get_setting_detail = AsyncMock(return_value=sample_setting_detail)
            mock_get_service.return_value = mock_service

            response = await async_client.get("/api/cloud/settings/PFUS_some_setting")

        assert response.status_code == 200
        data = response.json()
        assert "filament_id" in data

    async def test_get_setting_detail_not_found(self, async_client, test_db):
        """Test getting non-existent setting returns 404."""
        await test_db.set_setting("cloud_access_token", "valid-token")

        with patch('api.cloud.get_cloud_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.is_authenticated = True
            mock_service.get_setting_detail = AsyncMock(return_value=None)
            mock_get_service.return_value = mock_service

            response = await async_client.get("/api/cloud/settings/unknown-setting")

        assert response.status_code == 404

    async def test_get_setting_detail_unauthenticated(self, async_client, test_db):
        """Test getting setting detail without auth returns 401."""
        await test_db.delete_setting("cloud_access_token")

        response = await async_client.get("/api/cloud/settings/some-setting")

        assert response.status_code == 401


class TestCloudFilamentsAPI:
    """Tests for filament presets convenience endpoint."""

    async def test_get_filament_presets(self, async_client, test_db, sample_slicer_settings):
        """Test getting filament presets."""
        await test_db.set_setting("cloud_access_token", "valid-token")

        with patch('api.cloud.get_cloud_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.is_authenticated = True
            mock_service.get_slicer_settings = AsyncMock(return_value=sample_slicer_settings)
            mock_get_service.return_value = mock_service

            response = await async_client.get("/api/cloud/filaments")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
