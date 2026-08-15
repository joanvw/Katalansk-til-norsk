"""Tester for HTTP-backenden (uten nett for det meste; én ekte socket-tur)."""

import json
import os
import sys
import threading
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coach import RegelbasertAnalysator  # noqa: E402
from coach.web import behandle, lag_server  # noqa: E402


def _oppsett_dict() -> dict:
    return {
        "situasjon": "møte på jobben",
        "opplevd_rolle": "teamdeltager",
        "faktisk_rolle": "møteleder",
        "deltakere": [{"rolle": "leder"}, {"rolle": "motstander", "antall": 1}],
        "agenda": "diskusjon",
        "møtested": "på jobb",
        "ønskede_utkommer": ["et større felles eierskap"],
    }


# -- ren ruting ---------------------------------------------------------
def test_helse():
    status, data = behandle("GET", "/helse", None, RegelbasertAnalysator())
    assert status == 200 and data == {"status": "ok"}


def test_valg_lister_situasjoner_og_roller():
    status, data = behandle("GET", "/valg", None, RegelbasertAnalysator())
    assert status == 200
    tekster = [s["tekst"] for s in data["situasjoner"]]
    assert "møte på jobben" in tekster
    assert "leder" in data["roller"]
    # id-ene er stabile enum-navn
    assert any(s["id"] == "MØTE_JOBB" for s in data["situasjoner"])


def test_forbered_gir_drivere_og_tips():
    status, data = behandle("POST", "/forbered", _oppsett_dict(), RegelbasertAnalysator())
    assert status == 200
    assert "kontroll" in data["sannsynlige_drivere"]["leder"]
    assert data["møtetips"] and data["dialogtips"]


def test_analyser_gir_tilbakemelding():
    kropp = {
        "oppsett": _oppsett_dict(),
        "observasjoner": {
            "min_taletid_andel": 0.7,
            "antall_avbrytelser_fra_meg": 4,
            "naadde_utkommer": {"et større felles eierskap": False},
        },
    }
    status, data = behandle("POST", "/analyser", kropp, RegelbasertAnalysator())
    assert status == 200
    assert any("70 %" in f for f in data["forbedringsområder"])
    assert {p["rolle"] for p in data["per_deltaker"]} == {"leder", "motstander"}
    utkommer = {u["utkomme"] for u in data["utkomme_vurdering"]}
    assert "et større felles eierskap" in utkommer


# -- feilhåndtering -----------------------------------------------------
def test_ukjent_endepunkt_gir_404():
    from coach.web import HTTPFeil

    try:
        behandle("GET", "/finnes-ikke", None, RegelbasertAnalysator())
    except HTTPFeil as f:
        assert f.status == 404
    else:  # pragma: no cover
        raise AssertionError("forventet HTTPFeil 404")


def test_ugyldig_situasjon_gir_verdifeil():
    kropp = dict(_oppsett_dict(), situasjon="tulleverdi")
    try:
        behandle("POST", "/forbered", kropp, RegelbasertAnalysator())
    except ValueError as f:
        assert "Ugyldig Situasjon" in str(f)
    else:  # pragma: no cover
        raise AssertionError("forventet ValueError")


# -- én ekte socket-tur -------------------------------------------------
def test_ekte_http_kall():
    server = lag_server(port=0, analysator=RegelbasertAnalysator())
    port = server.server_address[1]
    tråd = threading.Thread(target=server.serve_forever, daemon=True)
    tråd.start()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/forbered",
            data=json.dumps(_oppsett_dict()).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as svar:
            assert svar.status == 200
            data = json.loads(svar.read().decode("utf-8"))
        assert "møtetips" in data
    finally:
        server.shutdown()
        server.server_close()
        tråd.join(timeout=5)


if __name__ == "__main__":
    import subprocess

    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", "-q", __file__]))
