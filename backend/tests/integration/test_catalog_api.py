"""
Integration tests for Spool Catalog API.

Tests cover:
- Get catalog entries
- Add/update/delete entries
- Reset to defaults
"""

import pytest


class TestCatalogAPI:
    """Tests for spool catalog CRUD operations."""

    async def test_get_catalog_default(self, async_client, test_db):
        """Test getting default catalog entries."""
        response = await async_client.get("/api/catalog")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should have some default entries
        assert len(data) > 0

    async def test_add_catalog_entry(self, async_client, test_db):
        """Test adding a new catalog entry."""
        entry = {"name": "Custom Spool", "weight": 250}

        response = await async_client.post("/api/catalog", json=entry)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Custom Spool"
        assert data["weight"] == 250
        assert data["is_default"] is False
        assert "id" in data

    async def test_update_catalog_entry(self, async_client, test_db):
        """Test updating a catalog entry."""
        # Create entry first
        entry = {"name": "To Update", "weight": 200}
        create_response = await async_client.post("/api/catalog", json=entry)
        entry_id = create_response.json()["id"]

        # Update it
        updated = {"name": "Updated Name", "weight": 300}
        response = await async_client.put(f"/api/catalog/{entry_id}", json=updated)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["weight"] == 300

    async def test_update_catalog_entry_not_found(self, async_client, test_db):
        """Test updating non-existent entry returns 404."""
        updated = {"name": "Does Not Exist", "weight": 100}

        response = await async_client.put("/api/catalog/99999", json=updated)

        assert response.status_code == 404

    async def test_delete_catalog_entry(self, async_client, test_db):
        """Test deleting a catalog entry."""
        # Create entry first
        entry = {"name": "To Delete", "weight": 150}
        create_response = await async_client.post("/api/catalog", json=entry)
        entry_id = create_response.json()["id"]

        # Delete it
        response = await async_client.delete(f"/api/catalog/{entry_id}")

        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

        # Verify it's gone from catalog
        catalog_response = await async_client.get("/api/catalog")
        catalog = catalog_response.json()
        assert not any(e["id"] == entry_id for e in catalog)

    async def test_delete_catalog_entry_not_found(self, async_client, test_db):
        """Test deleting non-existent entry returns 404."""
        response = await async_client.delete("/api/catalog/99999")

        assert response.status_code == 404

    async def test_reset_catalog(self, async_client, test_db):
        """Test resetting catalog to defaults."""
        # Add a custom entry
        entry = {"name": "Custom Entry", "weight": 500}
        await async_client.post("/api/catalog", json=entry)

        # Reset
        response = await async_client.post("/api/catalog/reset")

        assert response.status_code == 200
        assert response.json()["status"] == "reset"

        # Verify only default entries remain
        catalog_response = await async_client.get("/api/catalog")
        catalog = catalog_response.json()
        # All should be defaults
        for entry in catalog:
            assert entry["is_default"] is True

    async def test_catalog_entry_validation(self, async_client, test_db):
        """Test catalog entry validation."""
        # Missing required field
        invalid_entry = {"name": "No Weight"}

        response = await async_client.post("/api/catalog", json=invalid_entry)

        assert response.status_code == 422  # Validation error
