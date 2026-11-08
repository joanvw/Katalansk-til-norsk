"""Tester for X-Live-eksporten med et syntetisk SD-kort (ingen maskinvare)."""

import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from xlive_eksport import Valg, eksporter_alle, finn_sesjoner, les_scene_tekst  # noqa: E402
from xlive_eksport.eksport import parse_par, planlegg_spor, stereo_navn  # noqa: E402
from xlive_eksport.osc import osc_melding, tolk_svar  # noqa: E402
from xlive_eksport.wav import WavSkriver, del_ut_kanaler, les_wav_info  # noqa: E402

KANALER = 8
SR = 48000


def _verdi(kanal: int, frame: int) -> int:
    """Unik, gjenkjennelig 32-bit sampleverdi per kanal/frame."""
    v = ((kanal + 1) << 24) | ((frame & 0xFFFF) << 8) | 0x55
    return v - (1 << 32) if v >= 1 << 31 else v


def _skriv_take(sti: str, start: int, frames: int, header_ok: bool = True) -> None:
    data = struct.pack(f"<{frames * KANALER}i",
                       *(_verdi(c, start + f) for f in range(frames) for c in range(KANALER)))
    fmt = struct.pack("<HHIIHH", 1, KANALER, SR, SR * KANALER * 4, KANALER * 4, 32)
    storrelse = len(data) if header_ok else 0
    with open(sti, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", 4 + 24 + 8 + len(data)) + b"WAVE")
        f.write(b"fmt " + struct.pack("<I", 16) + fmt)
        f.write(b"data" + struct.pack("<I", storrelse) + data)


def _skriv_se_log(sti: str, markorer: list[int], navn: str) -> None:
    b = bytearray(2048)
    struct.pack_into("<IIIIII", b, 0, 0x4B2C1A10, KANALER, SR, 0, 2, len(markorer))
    for i, m in enumerate(markorer):
        struct.pack_into("<I", b, 1052 + 4 * i, m)
    b[1552:1552 + len(navn)] = navn.encode()
    with open(sti, "wb") as f:
        f.write(b)


SCENE = """#2.1# "Konsert" "" %000000000 1 X32
/ch/01/config "Kick" 1 RD 1
/ch/01/preamp +0.0 OFF ON 24 60.0
/ch/01/gate ON GATE -40.0 30.0 0 50.0 200 0
/ch/01/dyn ON COMP RMS LOG -18.0 4.0 2 3.00 10 10.0 151 POST 0 100 OFF
/ch/01/eq ON
/ch/01/eq/1 PEQ 62.0 +4.00 1.5
/ch/01/eq/2 PEQ 400.0 -6.00 2.0
/ch/01/mix ON -3.0 ON -20 OFF -oo
/ch/01/mix/13 ON -10.0 +0 POST
/ch/02/config "Snare" 1 YE 2
/ch/03/config "" 1 OFF 3
/ch/07/config "Keys L" 1 BL 7
/ch/08/config "Keys R" 1 BL 8
/config/chlink OFF OFF OFF ON OFF OFF OFF OFF OFF OFF OFF OFF OFF OFF OFF OFF
/config/routing/IN AN1-8 AN9-16 AN17-24 AN25-32 AUX/CR
/config/routing/CARD AN1-8 AN9-16 AN17-24 AN25-32
/headamp/000 +32.5 OFF
/fx/1 HALL
/fx/1/source MIX13 MIX13
/fx/1/par 40 1.8 60 5k74 25 0 85 -31 1.0 0 0 0
"""


@pytest.fixture
def kort(tmp_path):
    mappe = tmp_path / "SD" / "X_LIVE" / "4B2C1A10"
    mappe.mkdir(parents=True)
    _skriv_take(str(mappe / "00000001.WAV"), 0, 1000)
    _skriv_take(str(mappe / "00000002.WAV"), 1000, 500, header_ok=False)
    _skriv_se_log(str(mappe / "SE_LOG.BIN"), [480, 1200], "Lørdag")
    return tmp_path / "SD"


def _les_samples(sti: str) -> tuple[object, list[int]]:
    info = les_wav_info(sti)
    with open(sti, "rb") as f:
        f.seek(info.data_start)
        data = f.read(info.data_lengde)
    bps = info.bits // 8
    verdier = [int.from_bytes(data[i:i + bps], "little", signed=True)
               for i in range(0, len(data), bps)]
    return info, verdier


def test_finn_sesjon(kort):
    (s,) = finn_sesjoner(str(kort))
    assert s.kanaler == KANALER and s.samplerate == SR and s.bits == 32
    assert s.frames == 1500            # take 2 hadde ødelagt header
    assert s.markorer == [480, 1200]
    assert s.navn == "Lørdag"


def test_full_eksport(kort, tmp_path):
    scenefil = tmp_path / "konsert.scn"
    scenefil.write_text(SCENE, encoding="utf-8")
    ut = tmp_path / "ut"
    (s,) = finn_sesjoner(str(kort))
    ((_, mappe, planer),) = eksporter_alle([s], Valg(str(ut), scenefil=str(scenefil)), logg=lambda *_: None)

    navn = [p.filnavn for p in planer]
    assert navn == ["01 Kick.wav", "02 Snare.wav", "03 Ch 03.wav", "04 Ch 04.wav",
                    "05 Ch 05.wav", "06 Ch 06.wav", "07 Keys.wav"]
    assert planer[-1].stereo and planer[-1].kilder == [7, 8]

    # Mono: kanal 1 konvertert fra 32 til 24 bit, sammenhengende over begge takes.
    info, v = _les_samples(os.path.join(mappe, "01 Kick.wav"))
    assert (info.kanaler, info.bits, info.frames) == (1, 24, 1500)
    assert v == [_verdi(0, f) >> 8 for f in range(1500)]

    # Stereo: L = kanal 7, R = kanal 8.
    info, v = _les_samples(os.path.join(mappe, "07 Keys.wav"))
    assert info.kanaler == 2
    assert v[:4] == [_verdi(6, 0) >> 8, _verdi(7, 0) >> 8, _verdi(6, 1) >> 8, _verdi(7, 1) >> 8]

    # Markører ligger i WAV-filen.
    with open(os.path.join(mappe, "01 Kick.wav"), "rb") as f:
        raa = f.read()
    assert b"cue " in raa and b"Mark\xc3\xb8r 2" in raa

    filer = set(os.listdir(mappe))
    for forventet in ("spor.csv", "markorer.csv", "markorer.mid", "innstillinger.json",
                      "innstillinger.html", "LES_MEG.txt"):
        assert forventet in filer
    assert any(f.endswith(".RPP") for f in filer)

    data = json.load(open(os.path.join(mappe, "innstillinger.json"), encoding="utf-8"))
    kick = data["spor"][0]["kanaler"][0]
    assert kick["navn"] == "Kick"
    assert kick["kompressor"]["ratio"] == 4.0 and kick["kompressor"]["terskel_db"] == -18.0
    assert kick["gate"]["terskel_db"] == -40.0
    assert kick["eq"]["band"][1] == {"band": 2, "type": "PEQ", "freq_hz": 400.0, "gain_db": -6.0, "q": 2.0}
    assert kick["preamp"]["lavkutt_hz"] == 60.0
    assert kick["headamp"]["gain_db"] == 32.5
    assert kick["mix"]["fader_db"] == -3.0 and kick["mix"]["pan"] == -20
    assert data["effekter"][0]["type"] == "HALL"

    html = open(os.path.join(mappe, "innstillinger.html"), encoding="utf-8").read()
    assert "Kompressor" in html and "400 Hz" in html

    rpp = open(os.path.join(mappe, [f for f in filer if f.endswith(".RPP")][0]), encoding="utf-8").read()
    assert 'NAME "Kick"' in rpp and "MARKER 2 0.025000" in rpp


def test_uten_scene_og_valg(kort, tmp_path):
    (s,) = finn_sesjoner(str(kort))
    valg = Valg(str(tmp_path / "ut"), bits="samme", stereopar=parse_par("1-2"), hopp_over={8})
    ((_, mappe, planer),) = eksporter_alle([s], valg, logg=lambda *_: None)
    assert [p.filnavn for p in planer][:2] == ["01 Spor 01 + Spor 02.wav", "02 Spor 03.wav"]
    assert len(planer) == 6
    info, v = _les_samples(os.path.join(mappe, "02 Spor 03.wav"))
    assert info.bits == 32 and v[5] == _verdi(2, 5)


def test_routing_virtual_soundcheck():
    scene = les_scene_tekst([
        '/ch/01/config "Vokal" 1 RD 9',
        '/config/routing/IN CARD1-8 CARD9-16 AN17-24 AN25-32 AUX/CR',
        '/config/routing/CARD AN1-8 AN9-16 AN17-24 OUT1-8',
    ])
    mapping = scene.spormapping(32)
    assert mapping[8].kanal == 1          # spor 9 → inngang 9 → kanal 1
    assert mapping[24].etikett == "Out 1"
    planer = planlegg_spor(32, scene)
    assert planer[8].navn == "Vokal"


def test_hjelpefunksjoner():
    assert stereo_navn("OH L", "OH R") == "OH"
    assert stereo_navn("Gitar", "Bass") == "Gitar + Bass"
    with pytest.raises(ValueError):
        parse_par("3-5")
    buf = struct.pack("<4i", 0x01020304, 0x05060708, 0x11121314, 0x15161718)
    assert del_ut_kanaler(buf, 2, 4, [1], 3) == b"\x07\x06\x05\x17\x16\x15"
    adresse, args = tolk_svar(osc_melding("/node", "ch/01/config"))
    assert adresse == "/node" and args == ["ch/01/config"]


def test_rf64_header(tmp_path):
    sti = str(tmp_path / "x.wav")
    s = WavSkriver(sti, 1, SR, 24)
    s.skriv(b"\x00" * 30)
    s.data_byte = 0x1_0000_0000          # lat som filen er > 4 GB
    s.lukk()
    with open(sti, "rb") as f:
        hode = f.read(64)
    assert hode[:4] == b"RF64" and hode[12:16] == b"ds64"


# --------------------------------------------------------------------------
# USB: finn kort/scener og kopier råfiler
# --------------------------------------------------------------------------

from xlive_eksport.__main__ import hoved  # noqa: E402
from xlive_eksport.usb import Disk, finn_scenefiler, finn_xlive_kort, kopier_sesjon  # noqa: E402


def test_finn_kort_og_scene_paa_usb(kort, tmp_path):
    pinne = tmp_path / "PINNE"
    pinne.mkdir()
    (pinne / "Konsert.scn").write_text(SCENE, encoding="utf-8")
    disker = [Disk(str(kort), "XLIVE", True), Disk(str(pinne), "PINNE", True)]
    funnet = finn_xlive_kort(disker)
    assert [d.navn for d, _ in funnet] == ["XLIVE"]
    assert finn_scenefiler(disker) == [str(pinne / "Konsert.scn")]


def test_kopier_sesjon_gjenopptar_og_verifiserer(kort, tmp_path):
    (s,) = finn_sesjoner(str(kort))
    mal = tmp_path / "backup"
    hendelser = []
    kopi = kopier_sesjon(s, str(mal), lambda f, t, n: hendelser.append(n), verifiser=True)
    assert kopi.frames == s.frames and kopi.markorer == s.markorer
    assert sorted(os.listdir(mal / s.id)) == ["00000001.WAV", "00000002.WAV", "SE_LOG.BIN"]
    # Andre gang: alt finnes allerede og hoppes over.
    hendelser.clear()
    kopier_sesjon(s, str(mal), lambda f, t, n: hendelser.append(n))
    assert all(n.endswith("(finnes)") for n in hendelser)


def test_eksport_med_raakopi_og_cli(kort, tmp_path):
    ut = tmp_path / "ut"
    (s,) = finn_sesjoner(str(kort))
    ((kopi, mappe, _),) = eksporter_alle([s], Valg(str(ut), kopier_raa=True), logg=lambda *_: None)
    assert kopi.mappe.startswith(str(ut / "Råfiler"))
    assert os.path.exists(os.path.join(mappe, "01 Spor 01.wav"))
    assert hoved(["kopier", str(kort), "-o", str(tmp_path / "cli"), "--verifiser"]) == 0
    assert (tmp_path / "cli" / "Råfiler" / s.id / "00000001.WAV").exists()
    # Sikkerhetskopi lagret på selve kortet skal ikke telle som et nytt opptak.
    assert hoved(["kopier", str(kort), "-o", str(kort / "X-Live eksport")]) == 0
    assert len(finn_sesjoner(str(kort))) == 1


# --------------------------------------------------------------------------
# iPad: veiviser i terminalen og enkeltfil (.pyz)
# --------------------------------------------------------------------------

def test_veiviser_med_svar(kort, tmp_path, monkeypatch):
    from xlive_eksport import veiviser
    pinne = tmp_path / "scener"
    pinne.mkdir()
    (pinne / "Konsert.scn").write_text(SCENE, encoding="utf-8")
    monkeypatch.chdir(pinne)                 # scenen finnes i gjeldende mappe
    ut = tmp_path / "ut"
    svar = iter([str(kort), "", "1", str(ut), "", "", "n", "n", "j"])
    utskrift = []
    assert veiviser.kjor(lambda _: next(svar), utskrift.append) == 0
    (mappe,) = [d for d in os.listdir(ut)]
    assert "01 Kick.wav" in os.listdir(ut / mappe)
    assert any("Ferdig" in l for l in utskrift)


def test_pyz_kjorer(kort, tmp_path):
    import subprocess
    from xlive_eksport.bygg import bygg
    pyz = bygg(str(tmp_path / "xlive_eksport.pyz"))
    r = subprocess.run([sys.executable, "-I", pyz, "liste", str(kort)],
                       capture_output=True, text=True, cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr
    assert "Lørdag" in r.stdout
