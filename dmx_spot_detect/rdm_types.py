"""RDM-datatyper og klassifisering av armaturtype.

Definerer de RDM-konstantene (ANSI E1.20) og dataklassene som trengs for å
tolke svaret fra en armatur og avgjøre hvilken *type* spotter det er.

Selve typedeteksjonen bygger på RDM sitt standardiserte felt «Product
Category» i ``DEVICE_INFO``. Det er det nærmeste bransjen kommer en maskin-
lesbar «hva slags armatur er dette»-verdi.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


# --- RDM Parameter-ID-er (PID) vi bruker ---------------------------------
class PID(IntEnum):
    """Utvalg av standard RDM Parameter-ID-er fra ANSI E1.20."""

    DEVICE_INFO = 0x0060
    DEVICE_MODEL_DESCRIPTION = 0x0080
    MANUFACTURER_LABEL = 0x0081
    DEVICE_LABEL = 0x0082
    SOFTWARE_VERSION_LABEL = 0x00C0
    DMX_PERSONALITY_DESCRIPTION = 0x00E1
    DMX_START_ADDRESS = 0x00F0


# --- RDM Product Categories (ANSI E1.20, tabell A-5) ---------------------
class ProductCategory(IntEnum):
    """Standardiserte produktkategorier fra RDM DEVICE_INFO.

    Høybyten angir grovkategori, lavbyten en underkategori. Verdiene her er
    tatt direkte fra E1.20-standarden.
    """

    NOT_DECLARED = 0x0000

    FIXTURE = 0x0100
    FIXTURE_FIXED = 0x0101
    FIXTURE_MOVING_YOKE = 0x0102
    FIXTURE_MOVING_MIRROR = 0x0103
    FIXTURE_OTHER = 0x01FF

    FIXTURE_ACCESSORY = 0x0200

    PROJECTOR = 0x0300

    ATMOSPHERIC = 0x0400
    ATMOSPHERIC_EFFECT = 0x0401
    ATMOSPHERIC_PYRO = 0x0402

    DIMMER = 0x0500
    POWER = 0x0600
    SCENIC = 0x0700
    DATA = 0x0800
    AV = 0x0900
    MONITOR = 0x0A00

    CONTROL = 0x7000
    TEST = 0x7100
    OTHER = 0x7FFF

    @classmethod
    def _missing_(cls, value: object) -> "ProductCategory":
        """Ukjente verdier fanges opp av grovkategorien (høybyten)."""
        if isinstance(value, int):
            coarse = value & 0xFF00
            for member in cls:
                if member.value == coarse:
                    return member
        return cls.OTHER


# Menneskevennlige norske betegnelser per kategori.
_CATEGORY_LABELS_NO: dict[ProductCategory, str] = {
    ProductCategory.NOT_DECLARED: "Uoppgitt",
    ProductCategory.FIXTURE: "Armatur (uspesifisert)",
    ProductCategory.FIXTURE_FIXED: "Fast spotter (PAR/profil/wash)",
    ProductCategory.FIXTURE_MOVING_YOKE: "Moving head (bevegelig åk)",
    ProductCategory.FIXTURE_MOVING_MIRROR: "Scanner (bevegelig speil)",
    ProductCategory.FIXTURE_OTHER: "Armatur (annen type)",
    ProductCategory.FIXTURE_ACCESSORY: "Armaturtilbehør (gobo/fargeveksler)",
    ProductCategory.PROJECTOR: "Projektor",
    ProductCategory.ATMOSPHERIC: "Atmosfæreeffekt",
    ProductCategory.ATMOSPHERIC_EFFECT: "Effektmaskin (røyk/hazer)",
    ProductCategory.ATMOSPHERIC_PYRO: "Pyroteknikk",
    ProductCategory.DIMMER: "Dimmer",
    ProductCategory.POWER: "Strømstyring",
    ProductCategory.SCENIC: "Scenemekanikk",
    ProductCategory.DATA: "Datadistribusjon (splitter/node)",
    ProductCategory.AV: "AV-utstyr",
    ProductCategory.MONITOR: "Overvåking",
    ProductCategory.CONTROL: "Kontroller",
    ProductCategory.TEST: "Testutstyr",
    ProductCategory.OTHER: "Annet",
}


def category_label_no(category: ProductCategory) -> str:
    """Returner en norsk beskrivelse av produktkategorien."""
    return _CATEGORY_LABELS_NO.get(category, "Ukjent")


@dataclass(frozen=True, order=True)
class UID:
    """RDM Unique ID: 16-bit produsent-ID + 32-bit enhets-ID."""

    manufacturer_id: int
    device_id: int

    def __str__(self) -> str:  # f.eks. "4C56:00000123"
        return f"{self.manufacturer_id:04X}:{self.device_id:08X}"

    @classmethod
    def from_bytes(cls, data: bytes) -> "UID":
        if len(data) != 6:
            raise ValueError("En RDM UID må være nøyaktig 6 byte")
        manufacturer = int.from_bytes(data[0:2], "big")
        device = int.from_bytes(data[2:6], "big")
        return cls(manufacturer, device)


@dataclass
class DeviceInfo:
    """Tolket innhold av RDM GET DEVICE_INFO (PID 0x0060)."""

    rdm_protocol_version: int
    device_model_id: int
    product_category: ProductCategory
    software_version_id: int
    dmx_footprint: int
    current_personality: int
    personality_count: int
    dmx_start_address: int
    sub_device_count: int
    sensor_count: int

    @classmethod
    def from_bytes(cls, data: bytes) -> "DeviceInfo":
        """Tolk de 19 bytene i et DEVICE_INFO-svar."""
        if len(data) < 19:
            raise ValueError(
                f"DEVICE_INFO-svar for kort: fikk {len(data)} byte, forventet 19"
            )
        return cls(
            rdm_protocol_version=int.from_bytes(data[0:2], "big"),
            device_model_id=int.from_bytes(data[2:4], "big"),
            product_category=ProductCategory(int.from_bytes(data[4:6], "big")),
            software_version_id=int.from_bytes(data[6:10], "big"),
            dmx_footprint=int.from_bytes(data[10:12], "big"),
            current_personality=data[12],
            personality_count=data[13],
            dmx_start_address=int.from_bytes(data[14:16], "big"),
            sub_device_count=int.from_bytes(data[16:18], "big"),
            sensor_count=data[18],
        )


@dataclass
class DetectedFixture:
    """En armatur oppdaget og identifisert på DMX/RDM-linjen."""

    uid: UID
    device_info: DeviceInfo
    manufacturer_label: str = ""
    model_description: str = ""
    device_label: str = ""
    software_version_label: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def category(self) -> ProductCategory:
        return self.device_info.product_category

    @property
    def type_label(self) -> str:
        """Norsk betegnelse på spottertypen."""
        return category_label_no(self.category)

    @property
    def dmx_range(self) -> tuple[int, int]:
        """(startadresse, sluttadresse) armaturen okkuperer i universet."""
        start = self.device_info.dmx_start_address
        footprint = self.device_info.dmx_footprint
        end = start + max(footprint, 1) - 1
        return start, end

    def summary(self) -> str:
        maker = self.manufacturer_label or f"produsent {self.uid.manufacturer_id:#06x}"
        model = self.model_description or f"modell {self.device_info.device_model_id:#06x}"
        start, end = self.dmx_range
        return (
            f"{self.uid}  {self.type_label:<32}  {maker} {model}  "
            f"(DMX {start}-{end}, {self.device_info.dmx_footprint} kanaler)"
        )
