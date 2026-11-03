"""Hent gjeldende innstillinger direkte fra X32/M32 over nettverk.

Miksebordet svarer på OSC over UDP port 10023. Kommandoen
``/node ,s "ch/01/config"`` returnerer én tekstlinje i nøyaktig samme
format som scenefilen, så resultatet kan sendes rett til
``scene.les_scene_tekst``.

NB: Dette er miksebordets innstillinger *nå*, ikke nødvendigvis slik de
var under opptaket. Har du endret noe etterpå, bruk heller en scenefil
som ble lagret under konserten.
"""

from __future__ import annotations

import socket
import struct

PORT = 10023


def _osc_streng(s: str) -> bytes:
    b = s.encode() + b"\x00"
    return b + b"\x00" * (-len(b) % 4)


def osc_melding(adresse: str, *args: str) -> bytes:
    typer = "," + "s" * len(args)
    return _osc_streng(adresse) + _osc_streng(typer) + b"".join(_osc_streng(a) for a in args)


def _les_osc_streng(data: bytes, pos: int) -> tuple[str, int]:
    slutt = data.index(b"\x00", pos)
    tekst = data[pos:slutt].decode("utf-8", "replace")
    pos = slutt + 1
    pos += -pos % 4
    return tekst, pos


def tolk_svar(data: bytes) -> tuple[str, list]:
    adresse, pos = _les_osc_streng(data, 0)
    typer, pos = _les_osc_streng(data, pos)
    args: list = []
    for t in typer[1:]:
        if t == "s":
            s, pos = _les_osc_streng(data, pos)
            args.append(s)
        elif t == "i":
            args.append(struct.unpack(">i", data[pos:pos + 4])[0])
            pos += 4
        elif t == "f":
            args.append(struct.unpack(">f", data[pos:pos + 4])[0])
            pos += 4
    return adresse, args


def node_stier(kanaler: int = 32) -> list[str]:
    stier = ["config/chlink", "config/routing/IN", "config/routing/CARD"]
    for c in range(1, kanaler + 1):
        p = f"ch/{c:02d}"
        stier += [f"{p}/config", f"{p}/preamp", f"{p}/delay", f"{p}/gate",
                  f"{p}/gate/filter", f"{p}/dyn", f"{p}/dyn/filter", f"{p}/insert",
                  f"{p}/eq"] + [f"{p}/eq/{b}" for b in range(1, 5)] + [f"{p}/mix"]
        stier += [f"{p}/mix/{b:02d}" for b in range(1, 17)]
    stier += [f"headamp/{i:03d}" for i in range(128)]
    for fx in range(1, 9):
        stier += [f"fx/{fx}", f"fx/{fx}/source", f"fx/{fx}/par"]
    return stier


def hent_fra_miksebord(ip: str, tidsavbrudd: float = 0.5, logg=print) -> list[str]:
    """Spør miksebordet om alle relevante noder og returnér tekstlinjene."""
    stier = node_stier()
    linjer: list[str] = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(tidsavbrudd)
        s.sendto(osc_melding("/info"), (ip, PORT))
        try:
            data, _ = s.recvfrom(4096)
            _, args = tolk_svar(data)
            logg(f"Kontakt med miksebord: {' '.join(str(a) for a in args)}")
        except socket.timeout:
            raise ConnectionError(f"Ingen svar fra {ip}:{PORT} – sjekk IP og nettverk")
        for sti in stier:
            s.sendto(osc_melding("/node", sti), (ip, PORT))
            try:
                data, _ = s.recvfrom(4096)
            except socket.timeout:
                continue
            adresse, args = tolk_svar(data)
            if adresse == "/node" and args and isinstance(args[0], str):
                linjer += [l for l in args[0].splitlines() if l.strip()]
    logg(f"Hentet {len(linjer)} innstillinger fra {ip}")
    return linjer
