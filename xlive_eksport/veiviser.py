"""Veiviser i terminalen: spør steg for steg, ingen lange kommandoer.

Laget for iPad (a-Shell / Pythonista), der det ikke finnes noe vindu
(tkinter), men fungerer like godt på Mac, Windows og Linux::

    python -m xlive_eksport veiviser

Startes også automatisk når ``python -m xlive_eksport`` kjøres uten at
tkinter finnes.
"""

from __future__ import annotations

import os
import shutil
import sys
from typing import Callable

from .app import Valg, eksporter_alle
from .eksport import parse_par
from .sdkort import Sesjon, finn_sesjoner

Spor = Callable[[str], str]


def er_ipad() -> bool:
    """iPad/iPhone (a-Shell, Pythonista, Pyto): maskinnavnet er «iPad…»/«iPhone…»."""
    import platform
    return (sys.platform == "ios" or platform.machine().startswith(("iPad", "iPhone"))
            or os.environ.get("XLIVE_IPAD") == "1")


def _ja(svar: str, standard: bool) -> bool:
    svar = svar.strip().lower()
    if not svar:
        return standard
    return svar[0] in "jy"


def _gb(byte: float) -> str:
    return f"{byte / 1e9:.1f} GB"


def estimert_storrelse(sesjon: Sesjon, bits: int, spor: int) -> int:
    return sesjon.frames * spor * (bits // 8)


def _finn_scener(mapper: list[str]) -> list[str]:
    funnet: list[str] = []
    for m in mapper:
        if not os.path.isdir(m):
            continue
        basis = m.rstrip(os.sep).count(os.sep)
        for mappe, under, filer in os.walk(m):
            if mappe.count(os.sep) - basis >= 2:
                under[:] = []
            under[:] = [u for u in under if not u.startswith(".")]
            funnet += [os.path.join(mappe, f) for f in filer
                       if f.lower().endswith(".scn") and not f.startswith("._")]
    return sorted(set(funnet), key=os.path.getmtime, reverse=True)


def kjor(spor: Spor = input, skriv: Callable[[str], None] = print) -> int:
    skriv("\n=== X-Live eksport – X32 / M32 ===\n")
    if er_ipad():
        skriv("iPad: koble SD-kortet til med en USB-C-kortleser. I a-Shell skriver du\n"
              "først «pickFolder» og velger kortet, så står du i riktig mappe.\n")

    # 1. Kortet --------------------------------------------------------------
    standard = os.getcwd()
    while True:
        svar = spor(f"Mappe med X-Live-kortet [{standard}]: ").strip().strip('"')
        kort = os.path.expanduser(svar or standard)
        sesjoner = finn_sesjoner(kort) if os.path.isdir(kort) else []
        if sesjoner:
            break
        if not svar:
            try:
                from .usb import finn_xlive_kort
                usb = finn_xlive_kort()
            except Exception:  # noqa: BLE001
                usb = []
            if usb:
                kort = usb[0][0].sti
                sesjoner = [s for _, ss in usb for s in ss]
                skriv(f"Fant X-Live-kort på USB: {usb[0][0]}")
                break
        skriv(f"Fant ingen X-Live-opptak i «{kort}». Prøv igjen (Ctrl+C avbryter).")

    skriv(f"\nOpptak på kortet:")
    for i, s in enumerate(sesjoner, 1):
        skriv(f"{i:3d}. {s.beskrivelse()}")
    valgte = sesjoner
    svar = spor("\nHvilke vil du eksportere? (f.eks. 1,3 – Enter = alle): ").strip()
    if svar:
        nr = {int(x) for x in svar.replace(" ", "").split(",") if x.isdigit()}
        valgte = [s for i, s in enumerate(sesjoner, 1) if i in nr] or sesjoner

    # 2. Kanalnavn og innstillinger -----------------------------------------
    scener = _finn_scener([kort, os.getcwd(), os.path.expanduser("~/Documents")])
    skriv("\nKanalnavn, EQ, kompressor, gate og FX hentes fra:")
    valg_liste: list[tuple[str, str]] = [(f, "fil") for f in scener[:8]]
    for i, (f, _) in enumerate(valg_liste, 1):
        skriv(f"{i:3d}. Scenefil: {f}")
    skriv(f"{len(valg_liste) + 1:3d}. Miksebordet over nettverk (IP-adresse)")
    skriv(f"{len(valg_liste) + 2:3d}. Skriv inn sti til en scenefil")
    skriv(f"{len(valg_liste) + 3:3d}. Ingen (sporene heter Spor 01, Spor 02 …)")
    standard_valg = 1 if valg_liste else len(valg_liste) + 3
    svar = spor(f"Velg [{standard_valg}]: ").strip()
    n = int(svar) if svar.isdigit() else standard_valg
    scenefil = ip = None
    if 1 <= n <= len(valg_liste):
        scenefil = valg_liste[n - 1][0]
    elif n == len(valg_liste) + 1:
        ip = spor("IP-adressen til miksebordet (se SETUP > Network): ").strip() or None
    elif n == len(valg_liste) + 2:
        f = os.path.expanduser(spor("Sti til .scn-fil: ").strip().strip('"'))
        scenefil = f if os.path.isfile(f) else None
        if not scenefil:
            skriv("Fant ikke filen – fortsetter uten scene.")

    # 3. Målmappe -----------------------------------------------------------
    # iPad har lite lagring: standard er en mappe på selve kortet/disken.
    standard_ut = os.path.join(os.path.abspath(kort) if er_ipad() else os.path.expanduser("~"),
                               "X-Live eksport")
    svar = spor(f"\nHvor skal sporene lagres? [{standard_ut}]: ").strip().strip('"')
    ut = os.path.expanduser(svar or standard_ut)

    # 4. Valg ---------------------------------------------------------------
    bits_svar = spor("Bitdybde 24 eller 32? [24]: ").strip()
    bits = 32 if bits_svar == "32" else 24
    stereo = spor("Ekstra stereopar utover linkede kanaler (f.eks. 31-32, Enter = ingen): ")
    try:
        stereopar = parse_par(stereo)
    except ValueError as e:
        skriv(f"{e} – ignorerer.")
        stereopar = []
    fjern = _ja(spor("Fjerne spor som er helt stille? (j/n) [j]: "), True)
    kopier = _ja(spor("Kopiere råfilene fra kortet først som sikkerhetskopi? (j/n) [n]: "), False)

    valg = Valg(utmappe=ut, scenefil=scenefil, miksebord_ip=ip, bits=bits,
                stereopar=stereopar, fjern_stille=fjern, kopier_raa=kopier)

    # 5. Plass --------------------------------------------------------------
    behov = 0
    for s in valgte:
        behov += estimert_storrelse(s, min(bits, s.bits), s.kanaler)
        if kopier:
            behov += sum(t.data_lengde for t in s.takes)
    os.makedirs(ut, exist_ok=True)
    ledig = shutil.disk_usage(ut).free
    skriv(f"\nTrenger opptil {_gb(behov)} – ledig på målet: {_gb(ledig)}")
    if behov > ledig:
        skriv("ADVARSEL: Ikke nok plass! Velg en ekstern disk/SSD som mål, "
              "eller eksporter færre opptak.")
        if not _ja(spor("Fortsette likevel? (j/n) [n]: "), False):
            return 1

    if not _ja(spor(f"\nStarte eksport av {len(valgte)} opptak til «{ut}»? (j/n) [j]: "), True):
        return 1

    sist = [-1]

    def fremdrift(andel: float, tekst: str) -> None:
        p = int(andel * 100)
        if p != sist[0]:
            sist[0] = p
            print(f"\r   {p:3d} %  {tekst[:40]:<40}", end="", file=sys.stderr, flush=True)

    eksporter_alle(valgte, valg, logg=skriv, fremdrift=fremdrift)
    print(file=sys.stderr)
    skriv(f"\nFerdig! Åpne Filer-appen og gå til «{ut}».")
    if er_ipad():
        skriv("Sporene kan importeres i LumaFusion, Cubasis, Logic Pro for iPad, "
              "eller flyttes til datamaskinen med Pro Tools (se LES_MEG.txt).")
    return 0
