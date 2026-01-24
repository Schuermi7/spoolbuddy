"""Tag encoding/decoding module for NFC spool tags.

Supports:
- SpoolEase V2 tags (NTAG with NDEF URL)
- Bambu Lab tags (Mifare Classic 1K)
- OpenPrintTag tags (NTAG with NDEF CBOR)
- OpenSpool tags (NTAG with NDEF JSON)
- OpenTag3D tags (NTAG with NDEF binary)
"""

from .bambulab import BambuLabDecoder
from .decoder import TagDecoder
from .models import (
    BambuLabTagData,
    OpenPrintTagData,
    OpenSpoolTagData,
    SpoolEaseTagData,
    TagReadResult,
    TagType,
)
from .openprinttag import OpenPrintTagDecoder
from .openspool import OpenSpoolDecoder
from .opentag3d import OpenTag3DDecoder, OpenTag3DTagData
from .spoolease_format import SpoolEaseDecoder, SpoolEaseEncoder

__all__ = [
    "TagType",
    "TagReadResult",
    "SpoolEaseTagData",
    "BambuLabTagData",
    "OpenPrintTagData",
    "OpenSpoolTagData",
    "OpenTag3DTagData",
    "SpoolEaseDecoder",
    "SpoolEaseEncoder",
    "BambuLabDecoder",
    "OpenPrintTagDecoder",
    "OpenSpoolDecoder",
    "OpenTag3DDecoder",
    "TagDecoder",
]
