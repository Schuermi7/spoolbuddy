"""
Integration tests for Tag Encoding/Decoding API.

Tests cover:
- List tag formats
- Decode tag data
"""

import pytest


class TestTagFormatsAPI:
    """Tests for tag formats listing."""

    async def test_list_formats(self, async_client):
        """Test listing available tag formats."""
        response = await async_client.get("/api/tags/formats")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3  # SpoolEase, OpenSpool, OpenTag3D

        # Check format structure
        format_ids = [f["id"] for f in data]
        assert "SpoolEaseV2" in format_ids
        assert "OpenSpool" in format_ids
        assert "OpenTag3D" in format_ids

    async def test_format_info_structure(self, async_client):
        """Test that format info has all required fields."""
        response = await async_client.get("/api/tags/formats")

        assert response.status_code == 200
        data = response.json()

        for fmt in data:
            assert "id" in fmt
            assert "name" in fmt
            assert "description" in fmt
            assert "nfc_type" in fmt
            assert "min_capacity" in fmt
            assert "writable" in fmt

    async def test_spoolease_format_details(self, async_client):
        """Test SpoolEase format details."""
        response = await async_client.get("/api/tags/formats")
        data = response.json()

        spoolease = next(f for f in data if f["id"] == "SpoolEaseV2")
        assert spoolease["name"] == "SpoolEase V2"
        assert spoolease["writable"] is True
        assert "NTAG" in spoolease["nfc_type"]

    async def test_openspool_format_details(self, async_client):
        """Test OpenSpool format details."""
        response = await async_client.get("/api/tags/formats")
        data = response.json()

        openspool = next(f for f in data if f["id"] == "OpenSpool")
        assert openspool["name"] == "OpenSpool"
        assert openspool["writable"] is True
        assert "JSON" in openspool["description"]

    async def test_opentag3d_format_details(self, async_client):
        """Test OpenTag3D format details."""
        response = await async_client.get("/api/tags/formats")
        data = response.json()

        opentag3d = next(f for f in data if f["id"] == "OpenTag3D")
        assert opentag3d["name"] == "OpenTag3D"
        assert opentag3d["writable"] is True
        assert "binary" in opentag3d["description"].lower()


class TestTagDecodeAPI:
    """Tests for tag decoding endpoints."""

    async def test_decode_missing_payload(self, async_client):
        """Test decode fails when no payload provided."""
        decode_request = {
            "tag_uid": "01020304050607",
            # No url, json_payload, or payload_base64
        }
        response = await async_client.post("/api/tags/decode", json=decode_request)

        assert response.status_code == 400
        assert "Must provide one of" in response.json()["detail"]

    async def test_decode_returns_tag_uid(self, async_client):
        """Test decode response includes tag UID."""
        decode_request = {
            "tag_uid": "AABBCCDDEEFF00",
            "url": "https://example.com/test",  # Invalid URL, but tests UID handling
        }
        response = await async_client.post("/api/tags/decode", json=decode_request)

        assert response.status_code == 200
        data = response.json()
        assert data["tag_uid"] == "AABBCCDDEEFF00"
        assert "uid_base64" in data


class TestTagEncodeAPI:
    """Tests for tag encoding endpoints."""

    async def test_encode_spool_not_found(self, async_client, test_db):
        """Test encoding non-existent spool returns 404."""
        encode_request = {
            "spool_id": "nonexistent-spool-id",
            "format": "SpoolEaseV2",
        }
        response = await async_client.post("/api/tags/encode", json=encode_request)

        assert response.status_code == 404
        assert "Spool not found" in response.json()["detail"]

    async def test_encode_invalid_format(self, async_client, test_db):
        """Test encoding with invalid format."""
        # Create a spool
        spool = {"material": "PLA"}
        create_response = await async_client.post("/api/spools", json=spool)
        spool_id = create_response.json()["id"]

        # Try invalid format
        encode_request = {
            "spool_id": spool_id,
            "format": "InvalidFormat",
        }
        response = await async_client.post("/api/tags/encode", json=encode_request)

        assert response.status_code == 422  # Validation error
