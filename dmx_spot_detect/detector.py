"""Hoveddeteksjonen: finn og klassifiser spottere på en DMX/RDM-linje."""

from __future__ import annotations

from .rdm_types import (
    PID,
    DetectedFixture,
    DeviceInfo,
    ProductCategory,
    UID,
)
from .transport import RDMTransport


def _decode_label(data: bytes | None) -> str:
    """Tolk et RDM tekstfelt (ASCII, ev. null-terminert) trygt."""
    if not data:
        return ""
    return data.split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()


def identify_fixture(transport: RDMTransport, uid: UID) -> DetectedFixture | None:
    """Hent og tolk identiteten til én enhet.

    Returnerer ``None`` hvis enheten ikke svarer på det obligatoriske
    ``DEVICE_INFO`` – da kan vi ikke avgjøre typen.
    """
    raw_info = transport.rdm_get(uid, PID.DEVICE_INFO)
    if raw_info is None:
        return None

    try:
        info = DeviceInfo.from_bytes(raw_info)
    except ValueError as exc:
        # Ugyldig svar – lag en minimal oppføring med advarsel.
        info = DeviceInfo(
            rdm_protocol_version=0,
            device_model_id=0,
            product_category=ProductCategory.NOT_DECLARED,
            software_version_id=0,
            dmx_footprint=0,
            current_personality=0,
            personality_count=0,
            dmx_start_address=0,
            sub_device_count=0,
            sensor_count=0,
        )
        fixture = DetectedFixture(uid=uid, device_info=info)
        fixture.warnings.append(f"Kunne ikke tolke DEVICE_INFO: {exc}")
        return fixture

    fixture = DetectedFixture(
        uid=uid,
        device_info=info,
        manufacturer_label=_decode_label(
            transport.rdm_get(uid, PID.MANUFACTURER_LABEL)
        ),
        model_description=_decode_label(
            transport.rdm_get(uid, PID.DEVICE_MODEL_DESCRIPTION)
        ),
        device_label=_decode_label(transport.rdm_get(uid, PID.DEVICE_LABEL)),
        software_version_label=_decode_label(
            transport.rdm_get(uid, PID.SOFTWARE_VERSION_LABEL)
        ),
    )

    if info.product_category == ProductCategory.NOT_DECLARED:
        fixture.warnings.append(
            "Enheten oppgir ingen produktkategori – type kan ikke bestemmes "
            "sikkert fra RDM."
        )
    if info.dmx_footprint == 0:
        fixture.warnings.append("DMX-footprint er 0 (ren RDM-enhet uten DMX-kanaler?).")

    return fixture


def detect_fixtures(transport: RDMTransport) -> list[DetectedFixture]:
    """Oppdag og klassifiser alle spottere/armaturer på DMX-linjen.

    Dette er hovedfunksjonen. Den:

    1. kjører RDM-oppdaging for å finne alle enheter (UID-er) på linjen,
    2. spør hver enhet om ``DEVICE_INFO`` og navnefelt, og
    3. klassifiserer hver enhet til en spottertype via RDM Product Category.

    Merk: ren DMX512 er enveis og kan ikke oppdage koblede enheter. Denne
    funksjonen forutsetter derfor at ``transport`` støtter RDM (ANSI E1.20).

    Args:
        transport: En RDM-forbindelse (f.eks. ``OlaRDMTransport`` mot ekte
            maskinvare, eller ``MockRDMTransport`` i tester).

    Returns:
        Liste av ``DetectedFixture``, sortert på DMX-startadresse.
    """
    fixtures: list[DetectedFixture] = []
    for uid in transport.discover():
        fixture = identify_fixture(transport, uid)
        if fixture is not None:
            fixtures.append(fixture)

    fixtures.sort(key=lambda f: (f.device_info.dmx_start_address, f.uid))
    return fixtures
