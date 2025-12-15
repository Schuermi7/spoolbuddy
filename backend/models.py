from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ============ Spool Models ============

class SpoolBase(BaseModel):
    tag_id: Optional[str] = None
    material: str
    subtype: Optional[str] = None
    color_name: Optional[str] = None
    rgba: Optional[str] = None
    brand: Optional[str] = None
    label_weight: Optional[int] = 1000
    core_weight: Optional[int] = 250
    weight_new: Optional[int] = None
    weight_current: Optional[int] = None
    slicer_filament: Optional[str] = None
    note: Optional[str] = None
    data_origin: Optional[str] = None
    tag_type: Optional[str] = None


class SpoolCreate(SpoolBase):
    pass


class SpoolUpdate(SpoolBase):
    material: Optional[str] = None


class Spool(SpoolBase):
    id: str
    added_time: Optional[int] = None
    encode_time: Optional[int] = None
    added_full: Optional[int] = 0
    consumed_since_add: Optional[float] = 0
    consumed_since_weight: Optional[float] = 0
    created_at: Optional[int] = None
    updated_at: Optional[int] = None

    class Config:
        from_attributes = True


# ============ Printer Models ============

class PrinterBase(BaseModel):
    serial: str
    name: Optional[str] = None
    model: Optional[str] = None
    ip_address: Optional[str] = None
    access_code: Optional[str] = None
    auto_connect: bool = False


class PrinterCreate(PrinterBase):
    pass


class PrinterUpdate(BaseModel):
    name: Optional[str] = None
    model: Optional[str] = None
    ip_address: Optional[str] = None
    access_code: Optional[str] = None
    auto_connect: Optional[bool] = None


class Printer(PrinterBase):
    last_seen: Optional[int] = None
    config: Optional[str] = None

    class Config:
        from_attributes = True


class PrinterWithStatus(BaseModel):
    """Printer with connection status."""
    serial: str
    name: Optional[str] = None
    model: Optional[str] = None
    ip_address: Optional[str] = None
    access_code: Optional[str] = None
    last_seen: Optional[int] = None
    config: Optional[str] = None
    auto_connect: bool = False
    connected: bool = False


# ============ AMS Models ============

class AmsTray(BaseModel):
    """Single AMS tray/slot."""
    ams_id: int
    tray_id: int
    tray_type: Optional[str] = None
    tray_color: Optional[str] = None
    tray_info_idx: Optional[str] = None
    k_value: Optional[float] = None
    nozzle_temp_min: Optional[int] = None
    nozzle_temp_max: Optional[int] = None


class AmsUnit(BaseModel):
    """AMS unit with humidity and trays."""
    id: int
    humidity: Optional[int] = None
    temperature: Optional[int] = None
    extruder: Optional[int] = None  # 0 = right nozzle, 1 = left nozzle
    trays: list[AmsTray] = []


class PrinterState(BaseModel):
    """Real-time printer state from MQTT."""
    gcode_state: Optional[str] = None
    print_progress: Optional[int] = None
    layer_num: Optional[int] = None
    total_layer_num: Optional[int] = None
    subtask_name: Optional[str] = None
    ams_units: list[AmsUnit] = []
    vt_tray: Optional[AmsTray] = None


# ============ WebSocket Messages ============

class WSMessage(BaseModel):
    """WebSocket message wrapper."""
    type: str
    data: dict = {}
