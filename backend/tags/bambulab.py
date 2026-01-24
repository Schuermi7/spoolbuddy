"""Bambu Lab RFID tag decoder.

Bambu Lab uses Mifare Classic 1K tags with proprietary data storage.
The tag data is stored in specific blocks:

Block 1:
  - Offset 0-7: Material variant ID (e.g., "A00-G1")
  - Offset 8-15: Material ID (e.g., "GFA00")
Block 2:
  - Offset 0-15: Filament type (e.g., "PLA")
Block 4:
  - Offset 0-15: Detailed filament type (e.g., "PLA Basic")
Block 5:
  - Offset 0-3: Color RGBA (4 bytes)
  - Offset 4-5: Spool weight in grams (little-endian uint16)
Block 16:
  - Offset 2-3: Number of colors (little-endian int16)
  - Offset 4-7: Secondary color (reversed RGBA if num_colors > 1)

Note: Reading Bambu Lab tags requires the Crypto-1 authentication keys.
This decoder only parses the data once it's been read from the tag.
"""

import logging

from .models import BambuLabTagData, SpoolFromTag, TagType

logger = logging.getLogger(__name__)

# Bambu Lab material lookup tables
# Based on filaments_color_codes.json from BambuStudio
# Format: material_id -> (full_name, material_type)
BAMBU_MATERIALS = {
    "GFA00": ("Bambu PLA Basic", "PLA"),
    "GFA01": ("Bambu PLA Matte", "PLA"),
    "GFA02": ("Bambu PLA Metal", "PLA"),
    "GFA03": ("Bambu PLA Silk", "PLA"),
    "GFA05": ("Bambu PLA Tough", "PLA"),
    "GFA07": ("Bambu PLA Glow", "PLA"),
    "GFA08": ("Bambu PLA Sparkle", "PLA"),
    "GFA09": ("Bambu PLA Marble", "PLA"),
    "GFA50": ("Bambu PLA-CF", "PLA-CF"),
    "GFB00": ("Bambu ABS", "ABS"),
    "GFB01": ("Bambu ASA", "ASA"),
    "GFB60": ("Bambu ASA Aero", "ASA"),
    "GFB98": ("Bambu ABS-GF", "ABS-GF"),
    "GFB99": ("Support for ABS", "Support"),
    "GFC00": ("Bambu PC", "PC"),
    "GFG00": ("Bambu PETG Basic", "PETG"),
    "GFG01": ("Bambu PETG Translucent", "PETG"),
    "GFG50": ("Bambu PETG-CF", "PETG-CF"),
    "GFN03": ("Bambu PA-CF", "PA-CF"),
    "GFN04": ("Bambu PAHT-CF", "PAHT-CF"),
    "GFN05": ("Bambu PA6-CF", "PA6-CF"),
    "GFN06": ("Bambu PA6-GF", "PA6-GF"),
    "GFS00": ("Bambu Support W", "Support"),
    "GFS01": ("Bambu Support G", "Support"),
    "GFT00": ("Bambu TPU 95A", "TPU"),
    "GFU00": ("Bambu PLA-S", "PLA"),
    "GFU01": ("Bambu PET-CF", "PET-CF"),
    "GFL00": ("Generic PLA", "PLA"),
    "GFL01": ("Generic PETG", "PETG"),
    "GFL02": ("Generic ABS", "ABS"),
    "GFL03": ("Generic ASA", "ASA"),
    "GFL04": ("Generic PC", "PC"),
    "GFL05": ("Generic TPU", "TPU"),
    "GFL06": ("Generic PVA", "PVA"),
    "GFL99": ("Generic Filament", "PLA"),  # Default/unknown
}


class BambuLabDecoder:
    """Decoder for Bambu Lab RFID tags."""

    @staticmethod
    def decode(uid_hex: str, blocks: dict[int, bytes]) -> BambuLabTagData | None:
        """Decode Bambu Lab tag blocks to tag data.

        Args:
            uid_hex: Hex-encoded tag UID
            blocks: Dict mapping block number to block data (16 bytes each)

        Returns:
            Parsed tag data, or None if data is invalid
        """
        try:

            def get_cstr(data: bytes) -> str:
                """Extract null-terminated string from bytes."""
                null_pos = data.find(b"\x00")
                if null_pos >= 0:
                    data = data[:null_pos]
                return data.decode("utf-8", errors="ignore")

            # Material variant ID (Block 1, offset 0-7)
            material_variant_id = None
            if 1 in blocks and len(blocks[1]) >= 8:
                material_variant_id = get_cstr(blocks[1][0:8])

            # Material ID (Block 1, offset 8-15)
            material_id = None
            if 1 in blocks and len(blocks[1]) >= 16:
                material_id = get_cstr(blocks[1][8:16])

            # Filament type (Block 2)
            filament_type = None
            if 2 in blocks:
                filament_type = get_cstr(blocks[2])

            # Detailed filament type (Block 4)
            detailed_filament_type = None
            if 4 in blocks:
                detailed_filament_type = get_cstr(blocks[4])

            # Color RGBA (Block 5, offset 0-3)
            color_rgba = None
            if 5 in blocks and len(blocks[5]) >= 4:
                color_bytes = blocks[5][0:4]
                color_rgba = color_bytes.hex().upper()

            # Spool weight (Block 5, offset 4-5, little-endian)
            spool_weight = None
            if 5 in blocks and len(blocks[5]) >= 6:
                spool_weight = int.from_bytes(blocks[5][4:6], "little")
                if spool_weight == 0:
                    spool_weight = None

            # Secondary color (Block 16)
            color_rgba2 = None
            if 16 in blocks and len(blocks[16]) >= 8:
                block16 = blocks[16]
                num_colors = int.from_bytes(block16[2:4], "little")
                if num_colors > 1:
                    # Secondary color is stored reversed
                    color_rgba2 = bytes([block16[7], block16[6], block16[5], block16[4]]).hex().upper()

            return BambuLabTagData(
                tag_id=uid_hex.upper(),
                material_variant_id=material_variant_id,
                material_id=material_id,
                filament_type=filament_type,
                detailed_filament_type=detailed_filament_type,
                color_rgba=color_rgba,
                color_rgba2=color_rgba2,
                spool_weight=spool_weight,
                blocks=dict(blocks.items()),
            )

        except Exception as e:
            logger.error(f"Failed to decode Bambu Lab tag: {e}")
            return None

    @staticmethod
    def to_spool(data: BambuLabTagData) -> SpoolFromTag:
        """Convert Bambu Lab tag data to normalized spool data."""
        # Look up material info
        material_type = data.filament_type or "PLA"
        material_subtype = ""
        brand = "Bambu"

        if data.material_id and data.material_id in BAMBU_MATERIALS:
            full_name, mat_type = BAMBU_MATERIALS[data.material_id]
            material_type = mat_type

            # Extract subtype from full name
            prefix = f"Bambu {mat_type} "
            if full_name.startswith(prefix):
                material_subtype = full_name[len(prefix) :]
            elif full_name.startswith("Generic"):
                brand = "Generic"

        # Color name can be derived from color lookup tables
        # For now, use a placeholder
        color_name = "(Unknown Color)"
        if data.detailed_filament_type and data.color_rgba:
            color_name = f"{data.detailed_filament_type}"

        # Build note with missing fields
        missing = []
        if not data.color_rgba:
            missing.append("Color")
        if not data.spool_weight:
            missing.append("Spool Weight")
        note = f"Missing: {', '.join(missing)}" if missing else None

        return SpoolFromTag(
            tag_id=data.tag_id,
            tag_type=TagType.BAMBULAB.value,
            material=material_type,
            subtype=material_subtype,
            color_name=color_name,
            rgba=data.color_rgba,
            brand=brand,
            label_weight=1000 if data.material_id and data.material_id.startswith("GF") else None,
            core_weight=data.spool_weight,
            slicer_filament=data.material_id,
            note=note,
            data_origin=TagType.BAMBULAB.value,
        )
