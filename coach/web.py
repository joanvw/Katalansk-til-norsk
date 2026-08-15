"""HTTP-backend for coaching-appen (iPhone e.a.).

Eksponerer forberedelse og analyse over JSON slik at en mobilapp kan:

- hente valglistene til avkrysningsskjemaet   (GET  /valg)
- få forberedelse før treffet                 (POST /forbered)
- få tilbakemelding etter treffet             (POST /analyser)

Opptak av lyd/bilde og lagring skjer *på telefonen* (AVFoundation, Files/
iCloud); appen sender bare oppsett og transkripsjon hit. API-nøkkelen til
språkmodellen bor på serveren – aldri i appen.

Bygget på standardbiblioteket (`http.server`), så kjernen er
avhengighetsfri. Rutingen ligger i den rene funksjonen ``behandle`` slik at
den kan testes uten sockets; for produksjon kan du sette den bak en ekte
ASGI/WSGI-server, men logikken er den samme.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .ai_analysis import AIAnalysator, AnthropicKlient
from .analysis import Analysator, RegelbasertAnalysator
from .models import CoachingØkt
from .preparation import forbered
from .serde import (
    forberedelse_til_dict,
    observasjoner_fra_dict,
    oppsett_fra_dict,
    tilbakemelding_til_dict,
    valg_til_dict,
)


def standard_analysator() -> Analysator:
    """AI-analysator hvis en nøkkel finnes, ellers regelbasert.

    Faller alltid tilbake til ``RegelbasertAnalysator`` – både når nøkkel
    mangler, når SDK-et ikke er installert, og (via ``reserve``) hvis selve
    KI-kallet feiler underveis.
    """
    reserve = RegelbasertAnalysator()
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return AIAnalysator(AnthropicKlient(), reserve=reserve)
        except Exception:
            pass
    return reserve


class HTTPFeil(Exception):
    """Feil som skal svares som en gitt HTTP-status."""

    def __init__(self, status: int, melding: str):
        super().__init__(melding)
        self.status = status
        self.melding = melding


def behandle(
    metode: str,
    sti: str,
    kropp: dict | None,
    analysator: Analysator,
) -> tuple[int, dict]:
    """Ren ruting: (metode, sti, kropp) → (status, svar-dict).

    Kaster ``HTTPFeil`` for kjente feil (400/404/…); wrapperen oversetter.
    """
    if metode == "GET" and sti == "/helse":
        return 200, {"status": "ok"}
    if metode == "GET" and sti == "/valg":
        return 200, valg_til_dict()

    if metode == "POST" and sti == "/forbered":
        oppsett = oppsett_fra_dict(_krev_kropp(kropp))
        return 200, forberedelse_til_dict(forbered(oppsett))

    if metode == "POST" and sti == "/analyser":
        data = _krev_kropp(kropp)
        if "oppsett" not in data:
            raise HTTPFeil(400, "Mangler «oppsett» i forespørselen.")
        oppsett = oppsett_fra_dict(data["oppsett"])
        obs = observasjoner_fra_dict(data.get("observasjoner", {}))
        økt = CoachingØkt(oppsett=oppsett)
        tb = analysator.analyser(økt, obs)
        return 200, tilbakemelding_til_dict(tb)

    raise HTTPFeil(404, f"Ukjent endepunkt: {metode} {sti}")


def _krev_kropp(kropp: dict | None) -> dict:
    if kropp is None:
        raise HTTPFeil(400, "Forventet en JSON-kropp.")
    return kropp


def lag_handler(analysator: Analysator):
    """Bygg en BaseHTTPRequestHandler bundet til en gitt analysator."""

    class _Handler(BaseHTTPRequestHandler):
        server_version = "coach/1.0"

        # Slå av standard stderr-logging; la serveren styre det ved behov.
        def log_message(self, *_args):  # noqa: D401
            pass

        def _svar(self, status: int, data: dict) -> None:
            payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _kjør(self, metode: str) -> None:
            kropp = None
            if metode == "POST":
                lengde = int(self.headers.get("Content-Length") or 0)
                rå = self.rfile.read(lengde) if lengde else b""
                if rå:
                    try:
                        kropp = json.loads(rå.decode("utf-8"))
                    except json.JSONDecodeError:
                        self._svar(400, {"feil": "Ugyldig JSON."})
                        return
            try:
                status, data = behandle(metode, self.path, kropp, analysator)
            except HTTPFeil as feil:
                self._svar(feil.status, {"feil": feil.melding})
            except (ValueError, KeyError, TypeError) as feil:
                self._svar(400, {"feil": str(feil)})
            else:
                self._svar(status, data)

        def do_GET(self):  # noqa: N802
            self._kjør("GET")

        def do_POST(self):  # noqa: N802
            self._kjør("POST")

    return _Handler


def lag_server(port: int = 8000, analysator: Analysator | None = None) -> ThreadingHTTPServer:
    """Bygg (men start ikke) en HTTP-server bundet til alle grensesnitt."""
    handler = lag_handler(analysator or standard_analysator())
    return ThreadingHTTPServer(("", port), handler)


def kjør(port: int = 8000) -> None:
    analysator = standard_analysator()
    server = lag_server(port, analysator)
    navn = type(analysator).__name__
    print(f"coach-backend lytter på http://0.0.0.0:{port}  (analysator: {navn})")
    print("Endepunkter: GET /helse, GET /valg, POST /forbered, POST /analyser")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopper …")
    finally:
        server.server_close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Coach-backend (HTTP/JSON).")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    kjør(args.port)
