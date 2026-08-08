"""Tester for spotter-deteksjonen (kjører helt uten maskinvare)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dmx_spot_detect import (  # noqa: E402
    MockRDMTransport,
    PID,
    ProductCategory,
    UID,
    detect_fixtures,
)


def _device_info(
    category: ProductCategory,
    footprint: int = 8,
    start: int = 1,
    model: int = 0x0001,
) -> bytes:
    return (
        (0x0100).to_bytes(2, "big")
        + model.to_bytes(2, "big")
        + int(category).to_bytes(2, "big")
        + (0x00010000).to_bytes(4, "big")
        + footprint.to_bytes(2, "big")
        + (1).to_bytes(1, "big")
        + (1).to_bytes(1, "big")
        + start.to_bytes(2, "big")
        + (0).to_bytes(2, "big")
        + (0).to_bytes(1, "big")
    )


def test_uid_formatting_and_parsing():
    uid = UID.from_bytes(bytes.fromhex("4C5600000123"))
    assert uid == UID(0x4C56, 0x123)
    assert str(uid) == "4C56:00000123"


def test_detects_and_classifies_moving_head():
    transport = MockRDMTransport(
        {
            UID(0x4C56, 1): {
                PID.DEVICE_INFO: _device_info(
                    ProductCategory.FIXTURE_MOVING_YOKE, footprint=24, start=1
                ),
                PID.MANUFACTURER_LABEL: b"Acme\x00",
                PID.DEVICE_MODEL_DESCRIPTION: b"SpotBeam 300",
            }
        }
    )
    (fixture,) = detect_fixtures(transport)
    assert fixture.category == ProductCategory.FIXTURE_MOVING_YOKE
    assert fixture.type_label == "Moving head (bevegelig åk)"
    assert fixture.manufacturer_label == "Acme"  # null-terminering strippet
    assert fixture.model_description == "SpotBeam 300"
    assert fixture.dmx_range == (1, 24)
    assert fixture.warnings == []


def test_multiple_fixtures_sorted_by_start_address():
    transport = MockRDMTransport(
        {
            UID(0x4C56, 2): {
                PID.DEVICE_INFO: _device_info(ProductCategory.FIXTURE_FIXED, 8, start=25)
            },
            UID(0x4C56, 1): {
                PID.DEVICE_INFO: _device_info(
                    ProductCategory.FIXTURE_MOVING_YOKE, 24, start=1
                )
            },
        }
    )
    fixtures = detect_fixtures(transport)
    assert [f.uid for f in fixtures] == [UID(0x4C56, 1), UID(0x4C56, 2)]


def test_unknown_category_falls_back_to_coarse_group():
    # 0x0104 er ikke definert eksplisitt, men skal falle til FIXTURE (0x0100).
    transport = MockRDMTransport(
        {UID(0x4C56, 1): {PID.DEVICE_INFO: _device_info(ProductCategory(0x0104))}}
    )
    (fixture,) = detect_fixtures(transport)
    assert fixture.category == ProductCategory.FIXTURE


def test_device_without_device_info_is_skipped():
    transport = MockRDMTransport({UID(0x4C56, 1): {PID.MANUFACTURER_LABEL: b"Acme"}})
    assert detect_fixtures(transport) == []


def test_not_declared_category_produces_warning():
    transport = MockRDMTransport(
        {UID(0x4C56, 1): {PID.DEVICE_INFO: _device_info(ProductCategory.NOT_DECLARED)}}
    )
    (fixture,) = detect_fixtures(transport)
    assert any("produktkategori" in w for w in fixture.warnings)


if __name__ == "__main__":
    import subprocess

    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", "-q", __file__]))
