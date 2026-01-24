"""
Integration tests for Settings API.

Tests cover:
- Get/Set/Delete individual settings
- AMS threshold settings
"""

import pytest


class TestSettingsAPI:
    """Tests for basic settings CRUD operations."""

    async def test_get_setting_not_found(self, async_client, test_db):
        """Test getting a non-existent setting returns 404."""
        response = await async_client.get("/api/settings/nonexistent_key")

        assert response.status_code == 404
        assert "Setting not found" in response.json()["detail"]

    async def test_set_and_get_setting(self, async_client, test_db):
        """Test setting and retrieving a value."""
        # Set the setting
        response = await async_client.put("/api/settings/test_key", json={"value": "test_value"})

        assert response.status_code == 200
        data = response.json()
        assert data["key"] == "test_key"
        assert data["value"] == "test_value"

        # Get the setting
        response = await async_client.get("/api/settings/test_key")

        assert response.status_code == 200
        data = response.json()
        assert data["key"] == "test_key"
        assert data["value"] == "test_value"

    async def test_update_setting(self, async_client, test_db):
        """Test updating an existing setting."""
        # Set initial value
        await async_client.put("/api/settings/update_test", json={"value": "initial"})

        # Update value
        response = await async_client.put("/api/settings/update_test", json={"value": "updated"})

        assert response.status_code == 200
        assert response.json()["value"] == "updated"

        # Verify update
        response = await async_client.get("/api/settings/update_test")
        assert response.json()["value"] == "updated"

    async def test_delete_setting(self, async_client, test_db):
        """Test deleting a setting."""
        # Create setting first
        await async_client.put("/api/settings/delete_test", json={"value": "to_delete"})

        # Delete it
        response = await async_client.delete("/api/settings/delete_test")

        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

        # Verify deleted
        response = await async_client.get("/api/settings/delete_test")
        assert response.status_code == 404

    async def test_delete_setting_not_found(self, async_client, test_db):
        """Test deleting a non-existent setting returns 404."""
        response = await async_client.delete("/api/settings/nonexistent_delete")

        assert response.status_code == 404


class TestAMSThresholdsAPI:
    """Tests for AMS threshold settings."""

    async def test_get_default_thresholds(self, async_client, test_db):
        """Test getting default AMS thresholds when none are set."""
        response = await async_client.get("/api/settings/ams/thresholds")

        assert response.status_code == 200
        data = response.json()
        # Check defaults
        assert data["humidity_good"] == 40
        assert data["humidity_fair"] == 60
        assert data["temp_good"] == 28.0
        assert data["temp_fair"] == 35.0
        assert data["history_retention_days"] == 30

    async def test_set_ams_thresholds(self, async_client, test_db):
        """Test setting custom AMS thresholds."""
        thresholds = {
            "humidity_good": 30,
            "humidity_fair": 50,
            "temp_good": 25.0,
            "temp_fair": 32.0,
            "history_retention_days": 14,
        }

        response = await async_client.put("/api/settings/ams/thresholds", json=thresholds)

        assert response.status_code == 200
        data = response.json()
        assert data["humidity_good"] == 30
        assert data["humidity_fair"] == 50
        assert data["temp_good"] == 25.0
        assert data["temp_fair"] == 32.0
        assert data["history_retention_days"] == 14

    async def test_get_custom_thresholds(self, async_client, test_db):
        """Test retrieving custom AMS thresholds after setting them."""
        # Set custom thresholds
        thresholds = {
            "humidity_good": 35,
            "humidity_fair": 55,
            "temp_good": 26.0,
            "temp_fair": 33.0,
            "history_retention_days": 7,
        }
        await async_client.put("/api/settings/ams/thresholds", json=thresholds)

        # Retrieve and verify
        response = await async_client.get("/api/settings/ams/thresholds")

        assert response.status_code == 200
        data = response.json()
        assert data["humidity_good"] == 35
        assert data["humidity_fair"] == 55
        assert data["temp_good"] == 26.0
        assert data["temp_fair"] == 33.0
        assert data["history_retention_days"] == 7

    async def test_partial_threshold_update(self, async_client, test_db):
        """Test that all threshold fields are required in update."""
        # Pydantic will use defaults for missing fields
        thresholds = {
            "humidity_good": 45,
            # Missing other fields - will use defaults
        }

        response = await async_client.put("/api/settings/ams/thresholds", json=thresholds)

        assert response.status_code == 200
        data = response.json()
        assert data["humidity_good"] == 45
        # Others should be defaults
        assert data["humidity_fair"] == 60
