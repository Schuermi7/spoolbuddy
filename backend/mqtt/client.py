import json
import ssl
import logging
import asyncio
from typing import Optional, Callable, Any
from dataclasses import dataclass, field

import paho.mqtt.client as mqtt

from models import PrinterState, AmsUnit, AmsTray

logger = logging.getLogger(__name__)


@dataclass
class PrinterConnection:
    """Manages MQTT connection to a single Bambu printer."""

    serial: str
    ip_address: str
    access_code: str
    name: Optional[str] = None

    _client: Optional[mqtt.Client] = field(default=None, repr=False)
    _connected: bool = field(default=False, repr=False)
    _state: PrinterState = field(default_factory=PrinterState, repr=False)
    _on_state_update: Optional[Callable[[str, PrinterState], None]] = field(default=None, repr=False)
    _loop: Optional[asyncio.AbstractEventLoop] = field(default=None, repr=False)

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def state(self) -> PrinterState:
        return self._state

    def connect(self, on_state_update: Callable[[str, PrinterState], None]):
        """Connect to printer via MQTT."""
        self._on_state_update = on_state_update
        self._loop = asyncio.get_event_loop()

        # Create MQTT client
        self._client = mqtt.Client(
            client_id=f"spoolbuddy_{self.serial}",
            protocol=mqtt.MQTTv311,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )

        # Set credentials
        self._client.username_pw_set("bblp", self.access_code)

        # Configure TLS (Bambu printers use self-signed certs)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        self._client.tls_set_context(ssl_context)

        # Set callbacks
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        # Connect
        try:
            self._client.connect(self.ip_address, 8883, keepalive=60)
            self._client.loop_start()
            logger.info(f"Connecting to printer {self.serial} at {self.ip_address}")
        except Exception as e:
            logger.error(f"Failed to connect to {self.serial}: {e}")
            raise

    def disconnect(self):
        """Disconnect from printer."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False
            logger.info(f"Disconnected from printer {self.serial}")

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        """MQTT connect callback."""
        if reason_code == 0:
            self._connected = True
            logger.info(f"Connected to printer {self.serial}")

            # Subscribe to report topic
            topic = f"device/{self.serial}/report"
            client.subscribe(topic)
            logger.info(f"Subscribed to {topic}")

            # Request full state
            self._send_pushall()
        else:
            logger.error(f"Connection to {self.serial} failed: {reason_code}")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        """MQTT disconnect callback."""
        self._connected = False
        logger.info(f"Disconnected from printer {self.serial}: {reason_code}")

    def _on_message(self, client, userdata, msg):
        """MQTT message callback."""
        try:
            payload = json.loads(msg.payload.decode())
            self._handle_message(payload)
        except json.JSONDecodeError as e:
            logger.debug(f"Failed to parse message: {e}")
        except Exception as e:
            logger.error(f"Error handling message from {self.serial}: {e}")

    def _send_pushall(self):
        """Request full printer state."""
        if self._client and self._connected:
            topic = f"device/{self.serial}/request"
            payload = json.dumps({"pushing": {"command": "pushall", "sequence_id": "1"}})
            self._client.publish(topic, payload)

    def _handle_message(self, payload: dict):
        """Process incoming MQTT message."""
        if "print" not in payload:
            return

        print_data = payload["print"]

        # Extract gcode state
        if "gcode_state" in print_data:
            self._state.gcode_state = print_data["gcode_state"]

        # Extract progress (mc_percent is actual print progress)
        if "mc_percent" in print_data:
            self._state.print_progress = print_data["mc_percent"]

        # Extract subtask name
        if "subtask_name" in print_data:
            self._state.subtask_name = print_data["subtask_name"]

        # Extract layer info from nested "3D" object or direct fields
        data_3d = print_data.get("3D", {})
        if "layer_num" in data_3d:
            self._state.layer_num = data_3d["layer_num"]
        elif "layer_num" in print_data:
            self._state.layer_num = print_data["layer_num"]

        if "total_layer_num" in data_3d:
            self._state.total_layer_num = data_3d["total_layer_num"]
        elif "total_layer_num" in print_data:
            self._state.total_layer_num = print_data["total_layer_num"]

        # Extract AMS data
        if "ams" in print_data:
            self._parse_ams_data(print_data["ams"])

        # Extract virtual tray (external spool)
        if "vt_tray" in print_data:
            self._state.vt_tray = self._parse_tray(print_data["vt_tray"], 255, 0)

        # Notify listener
        if self._on_state_update:
            # Schedule callback in event loop if running from MQTT thread
            if self._loop:
                self._loop.call_soon_threadsafe(
                    lambda: self._on_state_update(self.serial, self._state)
                )

    def _parse_ams_data(self, ams_data: dict):
        """Parse AMS units and trays from MQTT data."""
        if "ams" not in ams_data:
            return

        units = []
        for ams_unit in ams_data["ams"]:
            unit_id = self._safe_int(ams_unit.get("id"), 0)
            humidity = self._safe_int(ams_unit.get("humidity"))
            temp = self._safe_int(ams_unit.get("temp"))

            # Extract extruder from info field: (info >> 8) & 0x0F
            info = self._safe_int(ams_unit.get("info"))
            extruder = ((info >> 8) & 0x0F) if info is not None else None

            # Parse trays
            trays = []
            for tray_data in ams_unit.get("tray", []):
                tray = self._parse_tray(tray_data, unit_id, self._safe_int(tray_data.get("id"), 0))
                if tray:
                    trays.append(tray)

            units.append(AmsUnit(
                id=unit_id,
                humidity=humidity,
                temperature=temp,
                extruder=extruder,
                trays=trays,
            ))

        self._state.ams_units = units

    def _parse_tray(self, tray_data: dict, ams_id: int, tray_id: int) -> Optional[AmsTray]:
        """Parse single tray data."""
        if not tray_data:
            return None

        return AmsTray(
            ams_id=ams_id,
            tray_id=tray_id,
            tray_type=tray_data.get("tray_type"),
            tray_color=tray_data.get("tray_color"),
            tray_info_idx=tray_data.get("tray_info_idx"),
            k_value=self._safe_float(tray_data.get("k")),
            nozzle_temp_min=self._safe_int(tray_data.get("nozzle_temp_min")),
            nozzle_temp_max=self._safe_int(tray_data.get("nozzle_temp_max")),
        )

    @staticmethod
    def _safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
        """Safely convert value to int."""
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
        """Safely convert value to float."""
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default


class PrinterManager:
    """Manages multiple printer connections."""

    def __init__(self):
        self._connections: dict[str, PrinterConnection] = {}
        self._on_state_update: Optional[Callable[[str, PrinterState], None]] = None

    def set_state_callback(self, callback: Callable[[str, PrinterState], None]):
        """Set callback for printer state updates."""
        self._on_state_update = callback

    async def connect(self, serial: str, ip_address: str, access_code: str, name: Optional[str] = None):
        """Connect to a printer."""
        if serial in self._connections:
            logger.warning(f"Printer {serial} already connected")
            return

        conn = PrinterConnection(
            serial=serial,
            ip_address=ip_address,
            access_code=access_code,
            name=name,
        )

        try:
            conn.connect(self._handle_state_update)
            self._connections[serial] = conn
        except Exception as e:
            logger.error(f"Failed to connect to {serial}: {e}")
            raise

    async def disconnect(self, serial: str):
        """Disconnect from a printer."""
        if serial not in self._connections:
            return

        conn = self._connections.pop(serial)
        conn.disconnect()

    async def disconnect_all(self):
        """Disconnect all printers."""
        for serial in list(self._connections.keys()):
            await self.disconnect(serial)

    def is_connected(self, serial: str) -> bool:
        """Check if printer is connected."""
        conn = self._connections.get(serial)
        return conn.connected if conn else False

    def get_state(self, serial: str) -> Optional[PrinterState]:
        """Get printer state."""
        conn = self._connections.get(serial)
        return conn.state if conn else None

    def get_connection_statuses(self) -> dict[str, bool]:
        """Get connection status for all managed printers."""
        return {serial: conn.connected for serial, conn in self._connections.items()}

    def _handle_state_update(self, serial: str, state: PrinterState):
        """Handle state update from printer."""
        if self._on_state_update:
            self._on_state_update(serial, state)
