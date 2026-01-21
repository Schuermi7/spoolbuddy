"""
Unit tests for Bambu Cloud service.

Tests cover:
- Authentication state management
- Login flow (with and without verification)
- Token management
- API calls (slicer settings, setting details)
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import httpx

from services.bambu_cloud import (
    BambuCloudService,
    BambuCloudError,
    BambuCloudAuthError,
    get_cloud_service,
)


class TestIsAuthenticated:
    """Tests for is_authenticated property."""

    def test_false_when_no_token(self):
        """Test is_authenticated returns False when no token."""
        service = BambuCloudService()
        assert service.is_authenticated is False

    def test_false_when_token_expired(self):
        """Test is_authenticated returns False when token expired."""
        service = BambuCloudService()
        service.access_token = "test-token"
        service.token_expiry = datetime.now() - timedelta(hours=1)
        assert service.is_authenticated is False

    def test_true_when_token_valid(self):
        """Test is_authenticated returns True when token valid."""
        service = BambuCloudService()
        service.access_token = "test-token"
        service.token_expiry = datetime.now() + timedelta(days=1)
        assert service.is_authenticated is True

    def test_true_when_no_expiry_but_has_token(self):
        """Test is_authenticated returns True when token exists without expiry."""
        service = BambuCloudService()
        service.access_token = "test-token"
        service.token_expiry = None
        assert service.is_authenticated is True


def _make_mock_response(status_code: int, json_data: dict) -> MagicMock:
    """Create a mock httpx response."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = json_data
    return mock_response


class TestLoginRequest:
    """Tests for login_request method."""

    @pytest.mark.asyncio
    async def test_verification_flow(self):
        """Test login that requires verification code."""
        service = BambuCloudService()

        mock_response = _make_mock_response(200, {"loginType": "verifyCode"})

        with patch.object(service._client, 'post', new=AsyncMock(return_value=mock_response)):
            result = await service.login_request("test@example.com", "password123")

        assert result["success"] is False
        assert result["needs_verification"] is True
        assert "Verification code" in result["message"]

    @pytest.mark.asyncio
    async def test_verification_flow_tfa_key(self):
        """Test login that requires 2FA (tfaKey response)."""
        service = BambuCloudService()

        mock_response = _make_mock_response(200, {"tfaKey": "some-tfa-key"})

        with patch.object(service._client, 'post', new=AsyncMock(return_value=mock_response)):
            result = await service.login_request("test@example.com", "password123")

        assert result["success"] is False
        assert result["needs_verification"] is True

    @pytest.mark.asyncio
    async def test_direct_login_success(self):
        """Test login that succeeds directly without verification."""
        service = BambuCloudService()

        mock_response = _make_mock_response(200, {"accessToken": "test-access-token"})

        with patch.object(service._client, 'post', new=AsyncMock(return_value=mock_response)):
            result = await service.login_request("test@example.com", "password123")

        assert result["success"] is True
        assert result["needs_verification"] is False
        assert service.access_token == "test-access-token"
        assert service.token_expiry is not None

    @pytest.mark.asyncio
    async def test_login_failure(self):
        """Test login failure with error message."""
        service = BambuCloudService()

        mock_response = _make_mock_response(401, {"message": "Invalid credentials"})

        with patch.object(service._client, 'post', new=AsyncMock(return_value=mock_response)):
            result = await service.login_request("test@example.com", "wrong-password")

        assert result["success"] is False
        assert result["needs_verification"] is False
        assert "Invalid credentials" in result["message"]

    @pytest.mark.asyncio
    async def test_login_network_error(self):
        """Test login raises error on network failure."""
        service = BambuCloudService()

        with patch.object(service._client, 'post', new=AsyncMock(side_effect=httpx.RequestError("Connection failed"))):
            with pytest.raises(BambuCloudAuthError) as exc_info:
                await service.login_request("test@example.com", "password123")

            assert "Login request failed" in str(exc_info.value)


class TestVerifyCode:
    """Tests for verify_code method."""

    @pytest.mark.asyncio
    async def test_verification_success(self):
        """Test successful verification sets tokens."""
        service = BambuCloudService()

        mock_response = _make_mock_response(200, {"accessToken": "verified-token"})

        with patch.object(service._client, 'post', new=AsyncMock(return_value=mock_response)):
            result = await service.verify_code("test@example.com", "123456")

        assert result["success"] is True
        assert service.access_token == "verified-token"
        assert service.token_expiry is not None

    @pytest.mark.asyncio
    async def test_verification_failure(self):
        """Test failed verification."""
        service = BambuCloudService()

        mock_response = _make_mock_response(400, {"message": "Invalid code"})

        with patch.object(service._client, 'post', new=AsyncMock(return_value=mock_response)):
            result = await service.verify_code("test@example.com", "000000")

        assert result["success"] is False
        assert "Invalid code" in result["message"]

    @pytest.mark.asyncio
    async def test_verification_network_error(self):
        """Test verification raises error on network failure."""
        service = BambuCloudService()

        with patch.object(service._client, 'post', new=AsyncMock(side_effect=httpx.RequestError("Timeout"))):
            with pytest.raises(BambuCloudAuthError) as exc_info:
                await service.verify_code("test@example.com", "123456")

            assert "Verification failed" in str(exc_info.value)


class TestTokenManagement:
    """Tests for token management methods."""

    def test_set_token_directly(self):
        """Test set_token sets access token and expiry."""
        service = BambuCloudService()

        service.set_token("direct-token")

        assert service.access_token == "direct-token"
        assert service.token_expiry is not None
        assert service.token_expiry > datetime.now()
        assert service.is_authenticated is True

    def test_logout_clears_state(self):
        """Test logout clears all authentication state."""
        service = BambuCloudService()
        service.access_token = "some-token"
        service.token_expiry = datetime.now() + timedelta(days=1)

        service.logout()

        assert service.access_token is None
        assert service.token_expiry is None
        assert service.is_authenticated is False

    def test_get_headers_without_token(self):
        """Test headers without auth token."""
        service = BambuCloudService()

        headers = service._get_headers()

        assert "Authorization" not in headers
        assert "Content-Type" in headers

    def test_get_headers_with_token(self):
        """Test headers include Bearer token when authenticated."""
        service = BambuCloudService()
        service.access_token = "my-token"

        headers = service._get_headers()

        assert headers["Authorization"] == "Bearer my-token"


class TestGetSlicerSettings:
    """Tests for get_slicer_settings method."""

    @pytest.mark.asyncio
    async def test_returns_settings(self):
        """Test get_slicer_settings returns parsed settings."""
        service = BambuCloudService()
        service.access_token = "valid-token"
        service.token_expiry = datetime.now() + timedelta(days=1)

        mock_response = _make_mock_response(200, {
            "filament": [{"setting_id": "GFSL05", "name": "PLA Basic"}],
            "printer": [{"setting_id": "BBL001", "name": "X1 Carbon"}],
        })

        with patch.object(service._client, 'get', new=AsyncMock(return_value=mock_response)):
            result = await service.get_slicer_settings()

        assert "filament" in result
        assert len(result["filament"]) == 1
        assert result["filament"][0]["setting_id"] == "GFSL05"

    @pytest.mark.asyncio
    async def test_requires_authentication(self):
        """Test get_slicer_settings raises error when not authenticated."""
        service = BambuCloudService()
        # No token set

        with pytest.raises(BambuCloudAuthError) as exc_info:
            await service.get_slicer_settings()

        assert "Not authenticated" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_uses_correct_version_param(self):
        """Test version parameter is passed correctly."""
        service = BambuCloudService()
        service.access_token = "valid-token"
        service.token_expiry = datetime.now() + timedelta(days=1)

        mock_get = AsyncMock(return_value=_make_mock_response(200, {"filament": []}))

        with patch.object(service._client, 'get', new=mock_get):
            await service.get_slicer_settings(version="01.00.00.00")

        # Check the version was passed in the URL
        call_args = mock_get.call_args
        assert "01.00.00.00" in str(call_args)


class TestGetSettingDetail:
    """Tests for get_setting_detail method."""

    @pytest.mark.asyncio
    async def test_returns_detail(self):
        """Test get_setting_detail returns setting details."""
        service = BambuCloudService()
        service.access_token = "valid-token"
        service.token_expiry = datetime.now() + timedelta(days=1)

        mock_response = _make_mock_response(200, {
            "setting_id": "custom-001",
            "filament_id": "GFSL05",
            "name": "My Custom PLA",
        })

        with patch.object(service._client, 'get', new=AsyncMock(return_value=mock_response)):
            result = await service.get_setting_detail("custom-001")

        assert "filament_id" in result
        assert result["filament_id"] == "GFSL05"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_authenticated(self):
        """Test get_setting_detail returns None when not authenticated."""
        service = BambuCloudService()
        # No token set

        result = await service.get_setting_detail("some-id")

        assert result is None


class TestGetCloudService:
    """Tests for singleton cloud service access."""

    def test_returns_same_instance(self):
        """Test get_cloud_service returns singleton instance."""
        service1 = get_cloud_service()
        service2 = get_cloud_service()

        assert service1 is service2

    def test_returns_bambu_cloud_service(self):
        """Test get_cloud_service returns BambuCloudService instance."""
        service = get_cloud_service()

        assert isinstance(service, BambuCloudService)
