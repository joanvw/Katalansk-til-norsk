"""Kommandolinje for X-Live-eksport (Behringer X32 / Midas M32).

Eksempler:
    python -m xlive_eksport                       # åpner GUI
    python -m xlive_eksport liste E:\\
    python -m xlive_eksport eksporter E:\\ -o D:\\Opptak --scene konsert.scn
    python -m xlive_eksport eksporter /Volumes/XLIVE -o ~/Opptak \\
        --miksebord 192.168.1.50 --stereo 31-32 --fjern-stille
"""

from __future__ import annotations

import argparse
import sys

from .app import Valg, eksporter_alle
from .eksport import parse_navnefil, parse_par, parse_tallsett as _tallsett
from .sdkort import finn_sesjoner


def _velg(sesjoner, valgte: list[str] | None):
    if not valgte:
        return sesjoner
    ut = []
    for v in valgte:
        treff = [s for s in sesjoner if v.lower() in (s.id.lower(), s.navn.lower())
                 or (v.isdigit() and int(v) == sesjoner.index(s) + 1)]
        if not treff:
            raise SystemExit(f"Fant ingen sesjon «{v}». Bruk «liste» for å se dem.")
        ut += [t for t in treff if t not in ut]
    return ut


def hoved(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="xlive_eksport",
        description="Kopier opptak fra X-Live-kort (X32/M32) til navngitte spor for DAW.")
    under = p.add_subparsers(dest="kommando")

    l = under.add_parser("liste", help="vis sesjonene på kortet")
    l.add_argument("kort", help="SD-kortets rotmappe (eller en sesjonsmappe)")

    e = under.add_parser("eksporter", help="eksporter sesjoner til spor")
    e.add_argument("kort", help="SD-kortets rotmappe (eller en sesjonsmappe)")
    e.add_argument("-o", "--ut", required=True, help="målmappe")
    e.add_argument("-s", "--sesjon", action="append",
                   help="bare denne sesjonen (nr. fra «liste», ID eller navn); kan gjentas")
    kilde = e.add_mutually_exclusive_group()
    kilde.add_argument("--scene", help="scenefil (.scn) lagret fra X32/M32")
    kilde.add_argument("--miksebord", metavar="IP", help="hent innstillinger fra miksebordet over nettverk")
    e.add_argument("--bits", default="24", choices=["16", "24", "32", "samme"],
                   help="bitdybde ut (standard 24 – Pro Tools-vennlig)")
    e.add_argument("--stereo", default="", help="ekstra stereopar, f.eks. 31-32,29-30")
    e.add_argument("--mono", default="", help="spor som alltid skal være mono, f.eks. 1-4,9")
    e.add_argument("--ingen-auto-stereo", action="store_true",
                   help="ikke lag stereo av linkede kanaler automatisk")
    e.add_argument("--navn", help="fil med «spor;navn» per linje som overstyrer navn")
    e.add_argument("--hopp-over", default="", help="spor som ikke skal eksporteres, f.eks. 25-30")
    e.add_argument("--fjern-stille", action="store_true",
                   help="slett spor som er helt digitalt stille (ingenting rutet)")

    under.add_parser("gui", help="åpne grafisk brukergrensesnitt")

    a = p.parse_args(argv)
    if a.kommando in (None, "gui"):
        from .gui import start
        start()
        return 0

    sesjoner = finn_sesjoner(a.kort)
    if not sesjoner:
        print(f"Fant ingen X-Live-sesjoner under {a.kort}")
        return 1
    if a.kommando == "liste":
        for i, s in enumerate(sesjoner, 1):
            print(f"{i:3d}. {s.beskrivelse()}")
        return 0

    valg = Valg(
        utmappe=a.ut, scenefil=a.scene, miksebord_ip=a.miksebord,
        bits=a.bits if a.bits == "samme" else int(a.bits),
        auto_stereo=not a.ingen_auto_stereo, stereopar=parse_par(a.stereo),
        monospor=_tallsett(a.mono), navn=parse_navnefil(a.navn) if a.navn else {},
        hopp_over=_tallsett(a.hopp_over), fjern_stille=a.fjern_stille)

    sist = [-1]

    def fremdrift(andel: float, tekst: str) -> None:
        prosent = int(andel * 100)
        if prosent != sist[0]:
            sist[0] = prosent
            print(f"\r   {prosent:3d} %  {tekst[:60]:<60}", end="", file=sys.stderr, flush=True)

    eksporter_alle(_velg(sesjoner, a.sesjon), valg, logg=print, fremdrift=fremdrift)
    print(file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(hoved())
