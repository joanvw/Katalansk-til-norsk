"""Kommandolinje for X-Live-eksport (Behringer X32 / Midas M32).

Eksempler:
    python -m xlive_eksport                       # åpner GUI
    python -m xlive_eksport usb                   # finn kort/scener på USB
    python -m xlive_eksport kopier -o D:\\Backup   # bare kopier råfilene via USB
    python -m xlive_eksport eksporter -o D:\\Opptak --scene auto --kopier-raa
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

KORT_HJELP = ("SD-kortets rotmappe eller en sesjonsmappe. Utelates den, letes det "
              "automatisk på alle USB-disker (kortleser)")


def _finn(kort: str | None):
    if kort:
        return finn_sesjoner(kort)
    from .usb import finn_xlive_kort
    funnet = finn_xlive_kort()
    for disk, sesjoner in funnet:
        print(f"X-Live-kort funnet på USB: {disk} – {len(sesjoner)} sesjon(er)")
    if not funnet:
        print("Fant ikke noe X-Live-kort på USB. Sett SD-kortet i en kortleser, "
              "eller oppgi mappen.")
    return [s for _, ss in funnet for s in ss]


def _fremdrift():
    sist = [-1]

    def fremdrift(andel: float, tekst: str) -> None:
        prosent = int(andel * 100)
        if prosent != sist[0]:
            sist[0] = prosent
            print(f"\r   {prosent:3d} %  {tekst[:60]:<60}", end="", file=sys.stderr, flush=True)
    return fremdrift


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
    l.add_argument("kort", nargs="?", help=KORT_HJELP)

    under.add_parser("usb", help="vis USB-disker, X-Live-kort og scenefiler som er koblet til")

    k = under.add_parser("kopier", help="kopier råfilene fra kortet til disk (sikkerhetskopi)")
    k.add_argument("kort", nargs="?", help=KORT_HJELP)
    k.add_argument("-o", "--ut", required=True, help="målmappe")
    k.add_argument("-s", "--sesjon", action="append", help="bare denne sesjonen; kan gjentas")
    k.add_argument("--verifiser", action="store_true", help="sammenlign kopien byte for byte")

    e = under.add_parser("eksporter", help="eksporter sesjoner til spor")
    e.add_argument("kort", nargs="?", help=KORT_HJELP)
    e.add_argument("-o", "--ut", required=True, help="målmappe")
    e.add_argument("-s", "--sesjon", action="append",
                   help="bare denne sesjonen (nr. fra «liste», ID eller navn); kan gjentas")
    kilde = e.add_mutually_exclusive_group()
    kilde.add_argument("--scene", help="scenefil (.scn) lagret fra X32/M32, "
                       "eller «auto» for nyeste .scn på USB-pinnen")
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
    e.add_argument("--kopier-raa", action="store_true",
                   help="kopier råfilene fra kortet til <målmappe>/Råfiler først")
    e.add_argument("--verifiser", action="store_true", help="med --kopier-raa: sjekk kopien byte for byte")

    under.add_parser("gui", help="åpne grafisk brukergrensesnitt")
    under.add_parser("veiviser", help="spør steg for steg i terminalen (iPad: a-Shell/Pythonista)")

    a = p.parse_args(argv)
    if a.kommando == "veiviser":
        from .veiviser import kjor
        return kjor()
    if a.kommando in (None, "gui"):
        try:
            import tkinter  # noqa: F401
        except ImportError:
            # Ingen vinduer (f.eks. iPad) → veiviser i terminalen.
            from .veiviser import kjor
            return kjor()
        from .gui import start
        start()
        return 0

    if a.kommando == "usb":
        from .usb import finn_scenefiler, finn_xlive_kort, usb_disker
        disker = usb_disker()
        print("USB-disker:" if disker else "Ingen USB-disker funnet.")
        for d in disker:
            print(f"   {d}")
        for disk, ss in finn_xlive_kort(disker):
            print(f"\nX-Live-kort på {disk}:")
            for i, s in enumerate(ss, 1):
                print(f"{i:3d}. {s.beskrivelse()}")
        scener = finn_scenefiler(disker)
        if scener:
            print("\nScenefiler (nyeste først):")
            for f in scener:
                print(f"   {f}")
        return 0

    sesjoner = _finn(a.kort)
    if not sesjoner:
        if a.kort:
            print(f"Fant ingen X-Live-sesjoner under {a.kort}")
        return 1
    if a.kommando == "liste":
        for i, s in enumerate(sesjoner, 1):
            print(f"{i:3d}. {s.beskrivelse()}")
        return 0

    if a.kommando == "kopier":
        from .app import kopier_raa
        valg = Valg(utmappe=a.ut, verifiser=a.verifiser)
        valgte = _velg(sesjoner, a.sesjon)
        fr = _fremdrift()
        for nr, s in enumerate(valgte, 1):
            print(f"[{nr}/{len(valgte)}] {s.beskrivelse()}")
            kopier_raa(s, valg, print, fr, nr, len(valgte))
            print(file=sys.stderr)
        return 0

    valg = Valg(
        utmappe=a.ut, scenefil=a.scene, miksebord_ip=a.miksebord,
        bits=a.bits if a.bits == "samme" else int(a.bits),
        auto_stereo=not a.ingen_auto_stereo, stereopar=parse_par(a.stereo),
        monospor=_tallsett(a.mono), navn=parse_navnefil(a.navn) if a.navn else {},
        hopp_over=_tallsett(a.hopp_over), fjern_stille=a.fjern_stille,
        kopier_raa=a.kopier_raa, verifiser=a.verifiser)

    eksporter_alle(_velg(sesjoner, a.sesjon), valg, logg=print, fremdrift=_fremdrift())
    print(file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(hoved())
