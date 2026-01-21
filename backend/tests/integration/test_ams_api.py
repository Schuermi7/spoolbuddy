"""
Integration tests for AMS API endpoints.

Tests cover:
- Setting filament on AMS slots
- Setting calibration profiles
- Resetting/clearing slots
- Assigning spools to slots
- Pending assignments
- Slot history
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock


class TestAmsFilamentAPI:
    """Tests for AMS filament setting endpoints."""

    async def test_set_filament_success(self, async_client, sample_printer_data, mock_printer_manager):
        """Test setting filament on an AMS slot."""
        # Create printer first
        await async_client.post("/api/printers", json=sample_printer_data)

        # Configure mock
        mock_printer_manager.is_connected.return_value = True
        mock_printer_manager.set_filament.return_value = True

        # Set filament
        response = await async_client.post(
            f"/api/printers/{sample_printer_data['serial']}/ams/0/tray/1/filament",
            json={
                "tray_info_idx": "GFL05",
                "setting_id": "GFSL05_07",
                "tray_type": "PLA",
                "tray_sub_brands": "Bambu PLA Basic",
                "tray_color": "FF0000FF",
                "nozzle_temp_min": 190,
                "nozzle_temp_max": 230,
            }
        )

        assert response.status_code == 204
        mock_printer_manager.set_filament.assert_called_once()

    async def test_set_filament_printer_not_connected(self, async_client, sample_printer_data, mock_printer_manager):
        """Test setting filament when printer not connected."""
        # Create printer first
        await async_client.post("/api/printers", json=sample_printer_data)

        # Configure mock
        mock_printer_manager.is_connected.return_value = False

        response = await async_client.post(
            f"/api/printers/{sample_printer_data['serial']}/ams/0/tray/0/filament",
            json={
                "tray_info_idx": "GFL05",
                "tray_type": "PLA",
                "tray_color": "FF0000FF",
                "nozzle_temp_min": 190,
                "nozzle_temp_max": 230,
            }
        )

        assert response.status_code == 400
        assert "not connected" in response.json()["detail"]

    async def test_set_filament_fails(self, async_client, sample_printer_data, mock_printer_manager):
        """Test setting filament when MQTT command fails."""
        await async_client.post("/api/printers", json=sample_printer_data)

        mock_printer_manager.is_connected.return_value = True
        mock_printer_manager.set_filament.return_value = False

        response = await async_client.post(
            f"/api/printers/{sample_printer_data['serial']}/ams/0/tray/0/filament",
            json={
                "tray_info_idx": "GFL05",
                "tray_type": "PLA",
                "tray_color": "FF0000FF",
                "nozzle_temp_min": 190,
                "nozzle_temp_max": 230,
            }
        )

        assert response.status_code == 500
        assert "Failed to set filament" in response.json()["detail"]


class TestAmsCalibrationAPI:
    """Tests for AMS calibration endpoints."""

    async def test_set_calibration_success(self, async_client, sample_printer_data, mock_printer_manager):
        """Test setting calibration profile on AMS slot."""
        await async_client.post("/api/printers", json=sample_printer_data)

        mock_printer_manager.is_connected.return_value = True
        mock_printer_manager.set_calibration.return_value = True

        response = await async_client.post(
            f"/api/printers/{sample_printer_data['serial']}/ams/0/tray/1/calibration",
            json={
                "cali_idx": 42,
                "filament_id": "GFL05",
                "nozzle_diameter": "0.4",
                "setting_id": "GFSL05_07",
                "k_value": 0.025,
                "nozzle_temp_max": 220,
            }
        )

        assert response.status_code == 204
        mock_printer_manager.set_calibration.assert_called_once()

    async def test_set_calibration_with_k_value(self, async_client, sample_printer_data, mock_printer_manager):
        """Test setting calibration also sets K value directly."""
        await async_client.post("/api/printers", json=sample_printer_data)

        mock_printer_manager.is_connected.return_value = True
        mock_printer_manager.set_calibration.return_value = True

        response = await async_client.post(
            f"/api/printers/{sample_printer_data['serial']}/ams/0/tray/2/calibration",
            json={
                "cali_idx": 42,
                "filament_id": "GFL05",
                "nozzle_diameter": "0.4",
                "k_value": 0.028,
                "nozzle_temp_max": 220,
            }
        )

        assert response.status_code == 204
        # Should call both set_calibration and set_k_value
        mock_printer_manager.set_calibration.assert_called_once()
        mock_printer_manager.set_k_value.assert_called_once()

    async def test_get_calibrations(self, async_client, sample_printer_data, mock_printer_manager, sample_calibration_profiles):
        """Test getting calibration profiles."""
        await async_client.post("/api/printers", json=sample_printer_data)

        mock_printer_manager.is_connected.return_value = True
        mock_printer_manager.get_kprofiles = AsyncMock(return_value=[
            {
                "cali_idx": 42,
                "filament_id": "GFL05",
                "k_value": 0.025,
                "name": "PLA Basic",
                "nozzle_diameter": "0.4",
            }
        ])

        response = await async_client.get(
            f"/api/printers/{sample_printer_data['serial']}/calibrations?nozzle_diameter=0.4"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["cali_idx"] == 42


class TestAmsResetAPI:
    """Tests for AMS slot reset endpoint."""

    async def test_reset_slot_success(self, async_client, sample_printer_data, mock_printer_manager):
        """Test resetting an AMS slot triggers RFID re-read."""
        await async_client.post("/api/printers", json=sample_printer_data)

        mock_printer_manager.is_connected.return_value = True
        mock_printer_manager.reset_slot.return_value = True

        response = await async_client.post(
            f"/api/printers/{sample_printer_data['serial']}/ams/0/tray/1/reset"
        )

        assert response.status_code == 204
        mock_printer_manager.reset_slot.assert_called_once_with(
            serial=sample_printer_data['serial'],
            ams_id=0,
            tray_id=1
        )

    async def test_reset_slot_not_connected(self, async_client, sample_printer_data, mock_printer_manager):
        """Test reset fails when printer not connected."""
        await async_client.post("/api/printers", json=sample_printer_data)

        mock_printer_manager.is_connected.return_value = False

        response = await async_client.post(
            f"/api/printers/{sample_printer_data['serial']}/ams/0/tray/0/reset"
        )

        assert response.status_code == 400

    async def test_reset_slot_fails(self, async_client, sample_printer_data, mock_printer_manager):
        """Test reset fails when MQTT command fails."""
        await async_client.post("/api/printers", json=sample_printer_data)

        mock_printer_manager.is_connected.return_value = True
        mock_printer_manager.reset_slot.return_value = False

        response = await async_client.post(
            f"/api/printers/{sample_printer_data['serial']}/ams/0/tray/0/reset"
        )

        assert response.status_code == 500


class TestAssignSpoolAPI:
    """Tests for spool-to-slot assignment endpoints."""

    async def test_assign_spool_immediate(self, async_client, test_db, sample_printer_data, mock_printer_manager, spool_factory):
        """Test assigning spool to occupied slot with matching spool."""
        await async_client.post("/api/printers", json=sample_printer_data)
        spool = await spool_factory(material="PLA", rgba="FF0000FF")

        # Mock printer state with occupied slot
        from models import PrinterState, AmsUnit, AmsTray
        mock_state = PrinterState(
            ams_units=[
                AmsUnit(
                    id=0,
                    humidity=35,
                    temperature=25.0,
                    trays=[
                        AmsTray(
                            ams_id=0,
                            tray_id=0,
                            tray_type="PLA",
                            tray_color="FF0000FF",
                            tray_info_idx="GFL05",
                        )
                    ]
                )
            ]
        )

        mock_printer_manager.is_connected.return_value = True
        mock_printer_manager.get_state.return_value = mock_state
        mock_printer_manager.set_filament.return_value = True
        mock_printer_manager.get_nozzle_diameter.return_value = "0.4"

        response = await async_client.post(
            f"/api/printers/{sample_printer_data['serial']}/ams/0/tray/0/assign",
            json={"spool_id": str(spool.id)}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "configured"

    async def test_assign_spool_staged(self, async_client, test_db, sample_printer_data, mock_printer_manager, spool_factory):
        """Test assigning spool to empty slot stages assignment."""
        await async_client.post("/api/printers", json=sample_printer_data)
        spool = await spool_factory(material="PETG", rgba="0000FFFF")

        # Mock printer state with empty slot
        from models import PrinterState, AmsUnit, AmsTray
        mock_state = PrinterState(
            ams_units=[
                AmsUnit(
                    id=0,
                    humidity=35,
                    temperature=25.0,
                    trays=[
                        AmsTray(ams_id=0, tray_id=0, tray_type=None)
                    ]
                )
            ]
        )

        mock_printer_manager.is_connected.return_value = True
        mock_printer_manager.get_state.return_value = mock_state
        mock_printer_manager.set_filament.return_value = True
        mock_printer_manager.get_nozzle_diameter.return_value = "0.4"

        response = await async_client.post(
            f"/api/printers/{sample_printer_data['serial']}/ams/0/tray/0/assign",
            json={"spool_id": str(spool.id)}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "staged"
        mock_printer_manager.stage_assignment.assert_called_once()

    async def test_assign_spool_not_found(self, async_client, sample_printer_data, mock_printer_manager):
        """Test assigning non-existent spool returns 404."""
        await async_client.post("/api/printers", json=sample_printer_data)

        mock_printer_manager.is_connected.return_value = True

        response = await async_client.post(
            f"/api/printers/{sample_printer_data['serial']}/ams/0/tray/0/assign",
            json={"spool_id": "non-existent-spool-id"}
        )

        assert response.status_code == 404

    async def test_unassign_spool(self, async_client, test_db, sample_printer_data, mock_printer_manager, spool_factory):
        """Test removing spool assignment from slot."""
        await async_client.post("/api/printers", json=sample_printer_data)
        spool = await spool_factory()

        # Assign first
        await test_db.assign_spool_to_slot(str(spool.id), sample_printer_data['serial'], 0, 0)

        response = await async_client.delete(
            f"/api/printers/{sample_printer_data['serial']}/ams/0/tray/0/assign"
        )

        assert response.status_code == 204
        mock_printer_manager.cancel_assignment.assert_called_once_with(
            sample_printer_data['serial'], 0, 0
        )

    async def test_get_slot_assignments(self, async_client, test_db, sample_printer_data, spool_factory):
        """Test getting all slot assignments for printer."""
        await async_client.post("/api/printers", json=sample_printer_data)
        spool = await spool_factory()

        # Assign spool
        await test_db.assign_spool_to_slot(str(spool.id), sample_printer_data['serial'], 0, 0)

        response = await async_client.get(
            f"/api/printers/{sample_printer_data['serial']}/assignments"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    async def test_get_pending_assignments(self, async_client, sample_printer_data, mock_printer_manager):
        """Test getting pending staged assignments."""
        await async_client.post("/api/printers", json=sample_printer_data)

        mock_pending = {
            (0, 1): MagicMock(
                spool_id="spool-123",
                tray_type="PLA",
                tray_color="FF0000FF"
            )
        }
        mock_printer_manager.get_all_pending_assignments.return_value = mock_pending

        response = await async_client.get(
            f"/api/printers/{sample_printer_data['serial']}/pending-assignments"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["ams_id"] == 0
        assert data[0]["tray_id"] == 1

    async def test_cancel_staged_assignment(self, async_client, sample_printer_data, mock_printer_manager):
        """Test cancelling a staged assignment."""
        await async_client.post("/api/printers", json=sample_printer_data)

        mock_printer_manager.cancel_assignment.return_value = True

        response = await async_client.post(
            f"/api/printers/{sample_printer_data['serial']}/ams/0/tray/1/cancel-staged"
        )

        assert response.status_code == 204

    async def test_cancel_staged_assignment_not_found(self, async_client, sample_printer_data, mock_printer_manager):
        """Test cancelling non-existent staged assignment."""
        await async_client.post("/api/printers", json=sample_printer_data)

        mock_printer_manager.cancel_assignment.return_value = False

        response = await async_client.post(
            f"/api/printers/{sample_printer_data['serial']}/ams/0/tray/1/cancel-staged"
        )

        assert response.status_code == 404


class TestAmsHistoryAPI:
    """Tests for AMS sensor history endpoint."""

    async def test_get_ams_history(self, async_client, test_db, sample_printer_data):
        """Test getting AMS humidity/temperature history."""
        await async_client.post("/api/printers", json=sample_printer_data)

        response = await async_client.get(
            f"/api/printers/{sample_printer_data['serial']}/ams/0/history?hours=24"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["printer_serial"] == sample_printer_data['serial']
        assert data["ams_id"] == 0
        assert "data" in data

    async def test_get_ams_history_printer_not_found(self, async_client):
        """Test getting history for non-existent printer."""
        response = await async_client.get(
            "/api/printers/nonexistent/ams/0/history"
        )

        assert response.status_code == 404

    async def test_get_ams_history_clamps_hours(self, async_client, test_db, sample_printer_data):
        """Test history endpoint clamps hours to valid range."""
        await async_client.post("/api/printers", json=sample_printer_data)

        # Request more than max (168 hours)
        response = await async_client.get(
            f"/api/printers/{sample_printer_data['serial']}/ams/0/history?hours=500"
        )

        assert response.status_code == 200
