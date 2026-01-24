"""
Integration tests for API Keys API.

Tests cover:
- List API keys
- Create API key
- Get API key by ID
- Update API key
- Delete API key
"""

import pytest


class TestAPIKeysAPI:
    """Tests for API keys CRUD operations."""

    async def test_list_api_keys_empty(self, async_client, test_db):
        """Test listing API keys when none exist."""
        response = await async_client.get("/api/api-keys/")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    async def test_create_api_key(self, async_client, test_db):
        """Test creating a new API key."""
        key_data = {
            "name": "Test Key",
            "can_read": True,
            "can_write": False,
            "can_control": False,
        }

        response = await async_client.post("/api/api-keys/", json=key_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Key"
        assert data["can_read"] is True
        assert data["can_write"] is False
        assert data["can_control"] is False
        assert data["enabled"] is True
        assert "id" in data
        assert "key" in data  # Full key only returned on creation
        assert data["key"].startswith("sb_")  # SpoolBuddy prefix
        assert "key_prefix" in data
        assert len(data["key_prefix"]) == 8
        assert "created_at" in data

    async def test_create_api_key_with_all_permissions(self, async_client, test_db):
        """Test creating an API key with all permissions."""
        key_data = {
            "name": "Admin Key",
            "can_read": True,
            "can_write": True,
            "can_control": True,
        }

        response = await async_client.post("/api/api-keys/", json=key_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Admin Key"
        assert data["can_read"] is True
        assert data["can_write"] is True
        assert data["can_control"] is True

    async def test_create_api_key_default_permissions(self, async_client, test_db):
        """Test creating an API key with default permissions."""
        key_data = {
            "name": "Read-Only Key",
        }

        response = await async_client.post("/api/api-keys/", json=key_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Read-Only Key"
        # Default permissions: read=True, write=False, control=False
        assert data["can_read"] is True
        assert data["can_write"] is False
        assert data["can_control"] is False

    async def test_list_api_keys(self, async_client, test_db):
        """Test listing API keys after creation."""
        # Get current count
        initial_response = await async_client.get("/api/api-keys/")
        initial_count = len(initial_response.json())

        # Create some keys
        key_data_1 = {"name": "List Test Key 1"}
        key_data_2 = {"name": "List Test Key 2"}
        await async_client.post("/api/api-keys/", json=key_data_1)
        await async_client.post("/api/api-keys/", json=key_data_2)

        response = await async_client.get("/api/api-keys/")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should have 2 more keys than before
        assert len(data) == initial_count + 2
        # Keys should not include the full key value
        for key in data:
            assert "key" not in key
            assert "key_prefix" in key

    async def test_get_api_key_by_id(self, async_client, test_db):
        """Test getting an API key by ID."""
        # Create a key
        key_data = {"name": "Fetch Test Key"}
        create_response = await async_client.post("/api/api-keys/", json=key_data)
        key_id = create_response.json()["id"]

        # Get by ID
        response = await async_client.get(f"/api/api-keys/{key_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == key_id
        assert data["name"] == "Fetch Test Key"
        # Full key should not be returned on GET
        assert "key" not in data

    async def test_get_api_key_not_found(self, async_client, test_db):
        """Test getting a non-existent API key returns 404."""
        response = await async_client.get("/api/api-keys/99999")

        assert response.status_code == 404

    async def test_update_api_key_name(self, async_client, test_db):
        """Test updating an API key name."""
        # Create a key
        key_data = {"name": "Original Name"}
        create_response = await async_client.post("/api/api-keys/", json=key_data)
        key_id = create_response.json()["id"]

        # Update name
        update_data = {"name": "Updated Name"}
        response = await async_client.patch(f"/api/api-keys/{key_id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"

    async def test_update_api_key_permissions(self, async_client, test_db):
        """Test updating API key permissions."""
        # Create a key with limited permissions
        key_data = {"name": "Test Key", "can_write": False, "can_control": False}
        create_response = await async_client.post("/api/api-keys/", json=key_data)
        key_id = create_response.json()["id"]

        # Update permissions
        update_data = {"can_write": True, "can_control": True}
        response = await async_client.patch(f"/api/api-keys/{key_id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["can_write"] is True
        assert data["can_control"] is True

    async def test_update_api_key_disable(self, async_client, test_db):
        """Test disabling an API key."""
        # Create a key
        key_data = {"name": "To Disable Key"}
        create_response = await async_client.post("/api/api-keys/", json=key_data)
        key_id = create_response.json()["id"]
        assert create_response.json()["enabled"] is True

        # Disable it
        update_data = {"enabled": False}
        response = await async_client.patch(f"/api/api-keys/{key_id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False

    async def test_update_api_key_enable(self, async_client, test_db):
        """Test re-enabling a disabled API key."""
        # Create and disable a key
        key_data = {"name": "To Enable Key"}
        create_response = await async_client.post("/api/api-keys/", json=key_data)
        key_id = create_response.json()["id"]
        await async_client.patch(f"/api/api-keys/{key_id}", json={"enabled": False})

        # Re-enable it
        response = await async_client.patch(f"/api/api-keys/{key_id}", json={"enabled": True})

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True

    async def test_update_api_key_not_found(self, async_client, test_db):
        """Test updating a non-existent API key returns 404."""
        update_data = {"name": "Does Not Exist"}

        response = await async_client.patch("/api/api-keys/99999", json=update_data)

        assert response.status_code == 404

    async def test_update_api_key_no_fields(self, async_client, test_db):
        """Test updating with no fields returns 400."""
        # Create a key
        key_data = {"name": "Test Key"}
        create_response = await async_client.post("/api/api-keys/", json=key_data)
        key_id = create_response.json()["id"]

        # Update with empty body
        response = await async_client.patch(f"/api/api-keys/{key_id}", json={})

        assert response.status_code == 400
        assert "No fields to update" in response.json()["detail"]

    async def test_delete_api_key(self, async_client, test_db):
        """Test deleting an API key."""
        # Create a key
        key_data = {"name": "To Delete Key"}
        create_response = await async_client.post("/api/api-keys/", json=key_data)
        key_id = create_response.json()["id"]

        # Delete it
        response = await async_client.delete(f"/api/api-keys/{key_id}")

        assert response.status_code == 200
        assert response.json()["message"] == "API key deleted"

        # Verify it's gone
        get_response = await async_client.get(f"/api/api-keys/{key_id}")
        assert get_response.status_code == 404

    async def test_delete_api_key_not_found(self, async_client, test_db):
        """Test deleting a non-existent API key returns 404."""
        response = await async_client.delete("/api/api-keys/99999")

        assert response.status_code == 404

    async def test_create_api_key_validation_missing_name(self, async_client, test_db):
        """Test API key creation validation - missing name."""
        invalid_data = {
            "can_read": True,
        }

        response = await async_client.post("/api/api-keys/", json=invalid_data)

        assert response.status_code == 422  # Validation error

    async def test_api_key_prefix_matches_key(self, async_client, test_db):
        """Test that key_prefix matches the start of the full key."""
        key_data = {"name": "Prefix Test Key"}

        response = await async_client.post("/api/api-keys/", json=key_data)

        assert response.status_code == 200
        data = response.json()
        full_key = data["key"]
        key_prefix = data["key_prefix"]
        assert full_key.startswith(key_prefix)

    async def test_multiple_api_keys_unique(self, async_client, test_db):
        """Test that multiple API keys have unique values."""
        key_data = {"name": "Key"}

        response1 = await async_client.post("/api/api-keys/", json=key_data)
        response2 = await async_client.post("/api/api-keys/", json=key_data)

        assert response1.status_code == 200
        assert response2.status_code == 200

        key1 = response1.json()["key"]
        key2 = response2.json()["key"]

        # Keys should be different
        assert key1 != key2

    async def test_api_key_created_at_timestamp(self, async_client, test_db):
        """Test that created_at is a valid timestamp."""
        import time

        before = int(time.time())
        key_data = {"name": "Timestamp Test Key"}
        response = await async_client.post("/api/api-keys/", json=key_data)
        after = int(time.time())

        assert response.status_code == 200
        created_at = response.json()["created_at"]
        assert before <= created_at <= after + 1
