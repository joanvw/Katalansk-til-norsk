"""Kommandolinje: skann en DMX/RDM-linje og skriv ut oppdagede spottere.

Eksempel:
    python -m dmx_spot_detect --universe 1
    python -m dmx_spot_detect --demo      # kjør mot innebygd testdata
"""

from __future__ import annotations

import argparse
import sys

from .detector import detect_fixtures
from .transport import MockRDMTransport, OlaRDMTransport


def _demo_transport() -> MockRDMTransport:
    """Litt eksempeldata så CLI-en kan demonstreres uten maskinvare."""
    from .rdm_types import PID, ProductCategory, UID

    def device_info(model: int, category: ProductCategory, footprint: int, start: int) -> bytes:
        return (
            (0x0100).to_bytes(2, "big")          # RDM-protokollversjon
            + model.to_bytes(2, "big")           # modell-ID
            + int(category).to_bytes(2, "big")   # produktkategori
            + (0x00010000).to_bytes(4, "big")    # programvareversjon
            + footprint.to_bytes(2, "big")       # DMX-footprint
            + (1).to_bytes(1, "big")             # gjeldende personlighet
            + (3).to_bytes(1, "big")             # antall personligheter
            + start.to_bytes(2, "big")           # DMX-startadresse
            + (0).to_bytes(2, "big")             # antall underenheter
            + (0).to_bytes(1, "big")             # antall sensorer
        )

    return MockRDMTransport(
        {
            UID(0x4C56, 0x00000001): {
                PID.DEVICE_INFO: device_info(0x0010, ProductCategory.FIXTURE_MOVING_YOKE, 24, 1),
                PID.MANUFACTURER_LABEL: b"Demo Lighting",
                PID.DEVICE_MODEL_DESCRIPTION: b"SpotBeam 300",
            },
            UID(0x4C56, 0x00000002): {
                PID.DEVICE_INFO: device_info(0x0020, ProductCategory.FIXTURE_FIXED, 8, 25),
                PID.MANUFACTURER_LABEL: b"Demo Lighting",
                PID.DEVICE_MODEL_DESCRIPTION: b"LED PAR 64",
            },
            UID(0x4C56, 0x00000003): {
                PID.DEVICE_INFO: device_info(0x0030, ProductCategory.ATMOSPHERIC_EFFECT, 2, 33),
                PID.MANUFACTURER_LABEL: b"Demo Lighting",
                PID.DEVICE_MODEL_DESCRIPTION: b"HazePro",
            },
        }
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dmx_spot_detect",
        description="Oppdag og klassifiser spottere på en DMX/RDM-linje.",
    )
    parser.add_argument("--universe", type=int, default=1, help="OLA-universnummer (standard: 1)")
    parser.add_argument("--demo", action="store_true", help="Kjør mot innebygd testdata uten maskinvare")
    args = parser.parse_args(argv)

    if args.demo:
        transport = _demo_transport()
    else:
        transport = OlaRDMTransport(universe=args.universe)

    try:
        fixtures = detect_fixtures(transport)
    except ImportError:
        print(
            "Fant ikke OLA-bindingene. Installer Open Lighting Architecture, "
            "start 'olad', eller kjør med --demo.",
            file=sys.stderr,
        )
        return 2

    if not fixtures:
        print("Ingen RDM-enheter svarte på linjen.")
        return 1

    print(f"Fant {len(fixtures)} enhet(er):\n")
    for fixture in fixtures:
        print("  " + fixture.summary())
        for warning in fixture.warnings:
            print(f"      ⚠ {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
