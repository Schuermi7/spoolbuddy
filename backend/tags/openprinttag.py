"""OpenPrintTag decoder.

OpenPrintTag is an open standard for NFC-based filament identification.
It uses NDEF records with CBOR-encoded payload.

NDEF record type: "application/vnd.openprinttag"

CBOR structure:
- Meta region (optional):
  - 0: main_region_offset
  - 1: main_region_size
  - 2: aux_region_offset
  - 3: aux_region_size

- Main region (CBOR map):
  - 9: material_type (enum index)
  - 10: material_name
  - 11: brand_name
  - 16: nominal_netto_full_weight
  - 17: actual_netto_full_weight
  - 18: empty_container_weight
  - 19: primary_color (3-4 bytes RGB/RGBA)
  - 20-24: secondary_colors
  - 52: material_abbreviation

Material type enum:
  0=PLA, 1=PETG, 2=TPU, 3=ABS, 4=ASA, 5=PC, 6=PCTG, 7=PP, 8=PA6, 9=PA11,
  10=PA12, 11=PA66, 12=CPE, 13=TPE, 14=HIPS, 15=PHA, 16=PET, 17=PEI,
  18=PBT, 19=PVB, 20=PVA, 21=PEKK, 22=PEEK, 23=BVOH, 24=TPC, 25=PPS,
  26=PPSU, 27=PVC, 28=PEBA, 29=PVDF, 30=PPA, 31=PCL, 32=PES, 33=PMMA,
  34=POM, 35=PPE, 36=PS, 37=PSU, 38=TPI, 39=SBS
"""

import base64
import logging
from typing import Optional, List

from .models import OpenPrintTagData, SpoolFromTag, TagType

logger = logging.getLogger(__name__)

# Material type enum mapping
MATERIAL_TYPES = [
    "PLA", "PETG", "TPU", "ABS", "ASA", "PC", "PCTG", "PP", "PA6", "PA11",
    "PA12", "PA66", "CPE", "TPE", "HIPS", "PHA", "PET", "PEI", "PBT", "PVB",
    "PVA", "PEKK", "PEEK", "BVOH", "TPC", "PPS", "PPSU", "PVC", "PEBA", "PVDF",
    "PPA", "PCL", "PES", "PMMA", "POM", "PPE", "PS", "PSU", "TPI", "SBS",
]

# Slicer filament code mapping
MATERIAL_TO_SLICER = {
    "PLA": "GFL00",
    "PETG": "GFL01",
    "ABS": "GFL02",
    "ASA": "GFL03",
    "PC": "GFL04",
    "TPU": "GFL05",
    "PVA": "GFL06",
}


class OpenPrintTagDecoder:
    """Decoder for OpenPrintTag NDEF records."""

    RECORD_TYPE = "application/vnd.openprinttag"

    @staticmethod
    def can_decode(ndef_records: list) -> bool:
        """Check if NDEF contains an OpenPrintTag record."""
        for record in ndef_records:
            record_type = record.get("type", b"")
            if isinstance(record_type, bytes):
                record_type = record_type.decode("utf-8", errors="ignore")
            if record_type == OpenPrintTagDecoder.RECORD_TYPE:
                return True
        return False

    @staticmethod
    def decode(uid_hex: str, ndef_payload: bytes) -> Optional[OpenPrintTagData]:
        """Decode OpenPrintTag CBOR payload.

        Args:
            uid_hex: Hex-encoded tag UID
            ndef_payload: Raw NDEF record payload (CBOR data)

        Returns:
            Parsed tag data, or None if decoding fails
        """
        try:
            import cbor2
        except ImportError:
            logger.warning("cbor2 not installed, OpenPrintTag decoding unavailable")
            return None

        try:
            # Convert UID to base64
            uid_bytes = bytes.fromhex(uid_hex)
            uid_base64 = base64.urlsafe_b64encode(uid_bytes).decode("ascii").rstrip("=")

            # Decode CBOR
            # First try to decode meta region
            decoder_pos = 0
            meta = cbor2.loads(ndef_payload)
            main_region_offset = meta.get(0, decoder_pos)

            # If meta contains main_region_offset, decode main region
            if isinstance(main_region_offset, int) and main_region_offset > 0:
                main_data = cbor2.loads(ndef_payload[main_region_offset:])
            else:
                # No meta region, this is the main data
                main_data = meta

            # Extract fields
            material_name = main_data.get(10)
            brand_name = main_data.get(11)
            material_type_idx = main_data.get(9)

            material_type = None
            if material_type_idx is not None and 0 <= material_type_idx < len(MATERIAL_TYPES):
                material_type = MATERIAL_TYPES[material_type_idx]

            # Weights
            nominal_weight = main_data.get(16)
            actual_weight = main_data.get(17)
            empty_weight = main_data.get(18)

            # Colors (stored as bytes)
            def parse_color(color_bytes: Optional[bytes]) -> Optional[str]:
                if not color_bytes:
                    return None
                if len(color_bytes) == 3:
                    return color_bytes.hex().upper() + "FF"  # Add alpha
                elif len(color_bytes) == 4:
                    return color_bytes.hex().upper()
                return None

            primary_color = parse_color(main_data.get(19))

            secondary_colors = []
            for i in range(20, 25):
                color = parse_color(main_data.get(i))
                if color:
                    secondary_colors.append(color)

            return OpenPrintTagData(
                tag_id=uid_base64,
                material_name=material_name,
                material_type=material_type,
                brand_name=brand_name,
                primary_color=primary_color,
                secondary_colors=secondary_colors if secondary_colors else None,
                nominal_weight=nominal_weight,
                actual_weight=actual_weight,
                empty_weight=empty_weight,
            )

        except Exception as e:
            logger.error(f"Failed to decode OpenPrintTag: {e}")
            return None

    @staticmethod
    def to_spool(data: OpenPrintTagData) -> SpoolFromTag:
        """Convert OpenPrintTag data to normalized spool data."""
        # Extract color name from material_name by removing material type
        color_name = data.material_name or ""
        if data.material_type and color_name:
            # Remove material type from name to get color
            words = color_name.split()
            color_name = " ".join(
                w for w in words if w.upper() != data.material_type.upper()
            )

        # Get slicer filament code
        slicer_code = MATERIAL_TO_SLICER.get(data.material_type or "", "")

        # Build note with missing fields
        missing = []
        if not data.material_type:
            missing.append("Material")
        if not slicer_code:
            missing.append("Slicer Filament")
        if not color_name:
            missing.append("Color Name")
        if not data.primary_color:
            missing.append("RGBA Color")
        if not data.brand_name:
            missing.append("Brand")
        if not data.nominal_weight:
            missing.append("Label Weight")
        if not data.empty_weight:
            missing.append("Empty Weight")

        note = f"Missing: {', '.join(missing)}" if missing else None

        return SpoolFromTag(
            tag_id=data.tag_id,
            tag_type=TagType.OPENPRINTTAG.value,
            material=data.material_type,
            subtype=None,
            color_name=color_name if color_name else None,
            rgba=data.primary_color,
            brand=data.brand_name,
            label_weight=data.nominal_weight,
            core_weight=data.empty_weight,
            weight_new=data.actual_weight,
            slicer_filament=slicer_code if slicer_code else None,
            note=note,
            data_origin=TagType.OPENPRINTTAG.value,
        )
