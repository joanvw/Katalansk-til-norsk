"""dmx_spot_detect – oppdag og klassifiser spottere på en DMX/RDM-linje.

Rent DMX512 er enveis og kan ikke se hva som er koblet til. Denne pakken
bruker RDM (ANSI E1.20) over samme kabel til å oppdage armaturer og lese
typen deres fra RDM Product Category.
"""

from .detector import detect_fixtures, identify_fixture
from .rdm_types import (
    DetectedFixture,
    DeviceInfo,
    PID,
    ProductCategory,
    UID,
    category_label_no,
)
from .transport import MockRDMTransport, OlaRDMTransport, RDMTransport

__all__ = [
    "detect_fixtures",
    "identify_fixture",
    "DetectedFixture",
    "DeviceInfo",
    "PID",
    "ProductCategory",
    "UID",
    "category_label_no",
    "RDMTransport",
    "MockRDMTransport",
    "OlaRDMTransport",
]
