"""
Integration tests for Colors API.

Tests cover:
- Get color catalog
- Add/update/delete color entries
- Reset to defaults
- Lookup color by manufacturer and color name
- Search colors by manufacturer and/or material
"""

from unittest.mock import patch

import pytest


class TestColorsAPI:
    """Tests for color catalog CRUD operations."""

    async def test_get_color_catalog(self, async_client, test_db):
        """Test getting color catalog entries."""
        response = await async_client.get("/api/colors")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_add_color_entry(self, async_client, test_db):
        """Test adding a new color entry."""
        entry = {
            "manufacturer": "Bambu Lab",
            "color_name": "Jade White",
            "hex_color": "#FFFFFF",
            "material": "PLA",
        }

        response = await async_client.post("/api/colors", json=entry)

        assert response.status_code == 200
        data = response.json()
        assert data["manufacturer"] == "Bambu Lab"
        assert data["color_name"] == "Jade White"
        assert data["hex_color"] == "#FFFFFF"
        assert data["material"] == "PLA"
        assert data["is_default"] is False
        assert "id" in data

    async def test_add_color_entry_without_material(self, async_client, test_db):
        """Test adding a color entry without material."""
        entry = {
            "manufacturer": "Polymaker",
            "color_name": "Black",
            "hex_color": "#000000",
        }

        response = await async_client.post("/api/colors", json=entry)

        assert response.status_code == 200
        data = response.json()
        assert data["manufacturer"] == "Polymaker"
        assert data["color_name"] == "Black"
        assert data["hex_color"] == "#000000"
        assert data["material"] is None
        assert "id" in data

    async def test_update_color_entry(self, async_client, test_db):
        """Test updating a color entry."""
        # Create entry first
        entry = {
            "manufacturer": "Test Brand",
            "color_name": "Original Color",
            "hex_color": "#111111",
            "material": "PETG",
        }
        create_response = await async_client.post("/api/colors", json=entry)
        entry_id = create_response.json()["id"]

        # Update it
        updated = {
            "manufacturer": "Updated Brand",
            "color_name": "Updated Color",
            "hex_color": "#222222",
            "material": "ABS",
        }
        response = await async_client.put(f"/api/colors/{entry_id}", json=updated)

        assert response.status_code == 200
        data = response.json()
        assert data["manufacturer"] == "Updated Brand"
        assert data["color_name"] == "Updated Color"
        assert data["hex_color"] == "#222222"
        assert data["material"] == "ABS"

    async def test_update_color_entry_not_found(self, async_client, test_db):
        """Test updating non-existent entry returns 404."""
        updated = {
            "manufacturer": "Does Not Exist",
            "color_name": "Unknown",
            "hex_color": "#333333",
        }

        response = await async_client.put("/api/colors/99999", json=updated)

        assert response.status_code == 404

    async def test_delete_color_entry(self, async_client, test_db):
        """Test deleting a color entry."""
        # Create entry first
        entry = {
            "manufacturer": "To Delete Brand",
            "color_name": "To Delete",
            "hex_color": "#444444",
        }
        create_response = await async_client.post("/api/colors", json=entry)
        entry_id = create_response.json()["id"]

        # Delete it
        response = await async_client.delete(f"/api/colors/{entry_id}")

        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

        # Verify it's gone from catalog
        catalog_response = await async_client.get("/api/colors")
        catalog = catalog_response.json()
        assert not any(e["id"] == entry_id for e in catalog)

    async def test_delete_color_entry_not_found(self, async_client, test_db):
        """Test deleting non-existent entry returns 404."""
        response = await async_client.delete("/api/colors/99999")

        assert response.status_code == 404

    async def test_reset_color_catalog(self, async_client, test_db):
        """Test resetting color catalog to defaults."""
        # Add a custom entry
        entry = {
            "manufacturer": "Custom Manufacturer",
            "color_name": "Custom Color",
            "hex_color": "#555555",
        }
        await async_client.post("/api/colors", json=entry)

        # Reset
        response = await async_client.post("/api/colors/reset")

        assert response.status_code == 200
        assert response.json()["status"] == "reset"

        # Verify only default entries remain (custom entry should be gone)
        catalog_response = await async_client.get("/api/colors")
        catalog = catalog_response.json()
        # All should be defaults
        for e in catalog:
            assert e["is_default"] is True

    async def test_color_entry_validation_missing_manufacturer(self, async_client, test_db):
        """Test color entry validation - missing manufacturer."""
        invalid_entry = {
            "color_name": "Red",
            "hex_color": "#FF0000",
        }

        response = await async_client.post("/api/colors", json=invalid_entry)

        assert response.status_code == 422  # Validation error

    async def test_color_entry_validation_missing_color_name(self, async_client, test_db):
        """Test color entry validation - missing color_name."""
        invalid_entry = {
            "manufacturer": "Bambu Lab",
            "hex_color": "#FF0000",
        }

        response = await async_client.post("/api/colors", json=invalid_entry)

        assert response.status_code == 422  # Validation error

    async def test_color_entry_validation_missing_hex_color(self, async_client, test_db):
        """Test color entry validation - missing hex_color."""
        invalid_entry = {
            "manufacturer": "Bambu Lab",
            "color_name": "Red",
        }

        response = await async_client.post("/api/colors", json=invalid_entry)

        assert response.status_code == 422  # Validation error


class TestColorsLookup:
    """Tests for color lookup functionality."""

    async def test_lookup_color_found(self, async_client, test_db):
        """Test looking up an existing color."""
        # Add a color entry first
        entry = {
            "manufacturer": "Bambu Lab",
            "color_name": "Matte Black",
            "hex_color": "#1A1A1A",
            "material": "PLA",
        }
        await async_client.post("/api/colors", json=entry)

        # Look it up
        response = await async_client.get(
            "/api/colors/lookup", params={"manufacturer": "Bambu Lab", "color_name": "Matte Black"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["found"] is True
        assert data["hex_color"] == "#1A1A1A"
        assert data["material"] == "PLA"

    async def test_lookup_color_found_with_material(self, async_client, test_db):
        """Test looking up a color with material filter."""
        # Add color entries with different materials
        entry1 = {
            "manufacturer": "Bambu Lab",
            "color_name": "Red",
            "hex_color": "#FF0000",
            "material": "PLA",
        }
        entry2 = {
            "manufacturer": "Bambu Lab",
            "color_name": "Red",
            "hex_color": "#DD0000",
            "material": "PETG",
        }
        await async_client.post("/api/colors", json=entry1)
        await async_client.post("/api/colors", json=entry2)

        # Look up with material filter
        response = await async_client.get(
            "/api/colors/lookup", params={"manufacturer": "Bambu Lab", "color_name": "Red", "material": "PETG"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["found"] is True
        assert data["hex_color"] == "#DD0000"
        assert data["material"] == "PETG"

    async def test_lookup_color_not_found(self, async_client, test_db):
        """Test looking up a non-existent color."""
        response = await async_client.get(
            "/api/colors/lookup", params={"manufacturer": "Unknown Brand", "color_name": "Unknown Color"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["found"] is False
        assert data["hex_color"] is None


class TestColorsSearch:
    """Tests for color search functionality."""

    async def test_search_by_manufacturer(self, async_client, test_db):
        """Test searching colors by manufacturer."""
        # Add some color entries
        entries = [
            {"manufacturer": "Bambu Lab", "color_name": "White", "hex_color": "#FFFFFF"},
            {"manufacturer": "Bambu Lab", "color_name": "Black", "hex_color": "#000000"},
            {"manufacturer": "Polymaker", "color_name": "Blue", "hex_color": "#0000FF"},
        ]
        for entry in entries:
            await async_client.post("/api/colors", json=entry)

        # Search by manufacturer
        response = await async_client.get("/api/colors/search", params={"manufacturer": "Bambu"})

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2
        for entry in data:
            assert "Bambu" in entry["manufacturer"]

    async def test_search_by_material(self, async_client, test_db):
        """Test searching colors by material."""
        # Add some color entries with unique material names
        entries = [
            {"manufacturer": "Brand A", "color_name": "White", "hex_color": "#FFFFFF", "material": "UNIQUE_PLA_TEST"},
            {"manufacturer": "Brand B", "color_name": "Black", "hex_color": "#000000", "material": "UNIQUE_PETG_TEST"},
            {"manufacturer": "Brand C", "color_name": "Blue", "hex_color": "#0000FF", "material": "UNIQUE_PLA_TEST"},
        ]
        for entry in entries:
            await async_client.post("/api/colors", json=entry)

        # Search by material
        response = await async_client.get("/api/colors/search", params={"material": "UNIQUE_PLA_TEST"})

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2
        for entry in data:
            assert "UNIQUE_PLA_TEST" in entry["material"]

    async def test_search_by_manufacturer_and_material(self, async_client, test_db):
        """Test searching colors by both manufacturer and material."""
        # Add some color entries with unique identifiers
        entries = [
            {"manufacturer": "TestMfg123", "color_name": "White", "hex_color": "#FFFFFF", "material": "MAT_XYZ"},
            {"manufacturer": "TestMfg123", "color_name": "Black", "hex_color": "#000000", "material": "MAT_ABC"},
            {"manufacturer": "OtherMfg456", "color_name": "Blue", "hex_color": "#0000FF", "material": "MAT_XYZ"},
        ]
        for entry in entries:
            await async_client.post("/api/colors", json=entry)

        # Search by both
        response = await async_client.get(
            "/api/colors/search", params={"manufacturer": "TestMfg123", "material": "MAT_XYZ"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        for entry in data:
            assert "TestMfg123" in entry["manufacturer"]
            assert "MAT_XYZ" in entry["material"]

    async def test_search_no_filters(self, async_client, test_db):
        """Test search without any filters returns results."""
        # Add a color entry
        entry = {
            "manufacturer": "Test Brand",
            "color_name": "Test Color",
            "hex_color": "#AABBCC",
        }
        await async_client.post("/api/colors", json=entry)

        # Search with no filters
        response = await async_client.get("/api/colors/search")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should return at least the entry we added
        assert len(data) >= 1

    async def test_search_case_insensitive(self, async_client, test_db):
        """Test that search is case insensitive."""
        # Add a color entry
        entry = {
            "manufacturer": "BAMBU LAB",
            "color_name": "Test",
            "hex_color": "#123456",
            "material": "PLA",
        }
        await async_client.post("/api/colors", json=entry)

        # Search with lowercase
        response = await async_client.get("/api/colors/search", params={"manufacturer": "bambu lab"})

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        # Should find the entry regardless of case
        found = any("BAMBU LAB" in e["manufacturer"].upper() for e in data)
        assert found

    async def test_search_partial_match(self, async_client, test_db):
        """Test that search supports partial matching."""
        # Add a color entry
        entry = {
            "manufacturer": "Bambu Lab",
            "color_name": "Test",
            "hex_color": "#654321",
        }
        await async_client.post("/api/colors", json=entry)

        # Search with partial manufacturer name
        response = await async_client.get("/api/colors/search", params={"manufacturer": "ambu"})

        assert response.status_code == 200
        data = response.json()
        # Should find entries with partial match
        assert len(data) >= 1
