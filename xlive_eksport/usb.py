"""Finn X-Live-kort og scenefiler på USB-tilkoblede disker, og kopier råfiler.

X-Live-kortet viser *ikke* SD-kortene som disk over sin egen USB-kabel
(den USB-porten er et 32×32 lydkort). Kopiering via USB gjøres derfor
med en USB-kortleser: SD-kortet dukker opp som en vanlig disk, og denne
modulen finner den automatisk.

Det samme gjelder USB-minnepinnen fra miksebordets USB-port, der
scenefiler (``.scn``) lagres – de blir funnet og foreslått automatisk.
"""

from __future__ import annotations

import os
import shutil
import string
import sys
from dataclasses import dataclass
from typing import Callable

from .sdkort import Sesjon, finn_sesjoner, les_sesjon

BLOKK = 8 * 1024 * 1024


@dataclass
class Disk:
    sti: str
    navn: str
    flyttbar: bool

    def __str__(self) -> str:
        return f"{self.navn} ({self.sti})" if self.navn and self.navn != self.sti else self.sti


def _windows_disker() -> list[Disk]:
    import ctypes
    k32 = ctypes.windll.kernel32
    disker = []
    maske = k32.GetLogicalDrives()
    for i, bokstav in enumerate(string.ascii_uppercase):
        if not maske & (1 << i):
            continue
        rot = f"{bokstav}:\\"
        typ = k32.GetDriveTypeW(rot)        # 2 = flyttbar, 3 = fast, 4 = nett, 5 = CD
        if typ not in (2, 3) or bokstav == os.environ.get("SystemDrive", "C:")[0]:
            continue
        buf = ctypes.create_unicode_buffer(261)
        k32.GetVolumeInformationW(rot, buf, 261, None, None, None, None, 0)
        disker.append(Disk(rot, buf.value or rot, typ == 2))
    return disker


def _unix_disker() -> list[Disk]:
    kandidater: list[str] = []
    if sys.platform == "darwin":
        kandidater += [os.path.join("/Volumes", d) for d in _ls("/Volumes")]
    else:
        # /media/<disk>, /media/<bruker>/<disk>, /run/media/<bruker>/<disk>, /mnt/<disk>
        for basis in ("/media", "/run/media", "/mnt"):
            for d in _ls(basis):
                p = os.path.join(basis, d)
                if os.path.ismount(p):
                    kandidater.append(p)
                else:
                    kandidater += [os.path.join(p, u) for u in _ls(p)
                                   if os.path.isdir(os.path.join(p, u))]
    disker = []
    for p in kandidater:
        if os.path.isdir(p) and not os.path.islink(p) and os.path.realpath(p) != "/":
            disker.append(Disk(p, os.path.basename(p), True))
    return disker


def _ls(sti: str) -> list[str]:
    try:
        return sorted(d for d in os.listdir(sti) if not d.startswith("."))
    except OSError:
        return []


def usb_disker() -> list[Disk]:
    """Alle eksterne/flyttbare disker (USB-kortleser, minnepinne, ekstern disk)."""
    try:
        return _windows_disker() if os.name == "nt" else _unix_disker()
    except Exception:  # noqa: BLE001 – plattformkall kan feile; da finner vi bare ingenting
        return []


def finn_xlive_kort(disker: list[Disk] | None = None) -> list[tuple[Disk, list[Sesjon]]]:
    """Disker som inneholder X-Live-sesjoner."""
    funnet = []
    for d in disker if disker is not None else usb_disker():
        sesjoner = finn_sesjoner(d.sti, maks_dybde=2)
        if sesjoner:
            funnet.append((d, sesjoner))
    return funnet


def finn_scenefiler(disker: list[Disk] | None = None, maks_dybde: int = 3) -> list[str]:
    """``.scn``-filer på USB-disker (miksebordet lagrer dem på USB-pinnen)."""
    filer: list[str] = []
    for d in disker if disker is not None else usb_disker():
        basis = d.sti.rstrip(os.sep).count(os.sep)
        for mappe, under, navn in os.walk(d.sti):
            if mappe.count(os.sep) - basis >= maks_dybde:
                under[:] = []
            under[:] = [u for u in under if not u.startswith((".", "$", "System Volume"))]
            filer += [os.path.join(mappe, n) for n in navn
                      if n.lower().endswith(".scn") and not n.startswith("._")]
    return sorted(filer, key=lambda f: os.path.getmtime(f), reverse=True)


# --------------------------------------------------------------------------
# Kopiering av råfiler
# --------------------------------------------------------------------------

def kopier_sesjon(
    sesjon: Sesjon,
    malmappe: str,
    fremdrift: Callable[[int, int, str], None] | None = None,
    verifiser: bool = False,
) -> Sesjon:
    """Kopier en sesjonsmappe (WAV-takes + SE_LOG.BIN) fra kortet til disk.

    * Filer som allerede er kopiert (samme størrelse) hoppes over, så en
      avbrutt kopiering kan bare startes på nytt.
    * Kopien skrives til ``.del``-fil og døpes om når den er komplett.
    * ``verifiser=True`` leser begge filene på nytt og sammenligner innholdet.

    Returnerer sesjonen lest fra kopien, klar for eksport.
    """
    ut = os.path.join(malmappe, sesjon.id)
    os.makedirs(ut, exist_ok=True)
    filer = sorted(f for f in os.listdir(sesjon.mappe)
                   if os.path.isfile(os.path.join(sesjon.mappe, f)) and not f.startswith("."))
    totalt = sum(os.path.getsize(os.path.join(sesjon.mappe, f)) for f in filer)
    ferdig = 0
    for navn in filer:
        kilde = os.path.join(sesjon.mappe, navn)
        mal = os.path.join(ut, navn)
        storrelse = os.path.getsize(kilde)
        if os.path.exists(mal) and os.path.getsize(mal) == storrelse:
            ferdig += storrelse
            if fremdrift:
                fremdrift(ferdig, totalt, f"{navn} (finnes)")
            continue
        midlertidig = mal + ".del"
        with open(kilde, "rb") as fi, open(midlertidig, "wb") as fo:
            while True:
                b = fi.read(BLOKK)
                if not b:
                    break
                fo.write(b)
                ferdig += len(b)
                if fremdrift:
                    fremdrift(ferdig, totalt, navn)
            fo.flush()
            os.fsync(fo.fileno())
        if os.path.getsize(midlertidig) != storrelse:
            raise OSError(f"{navn}: kopien har feil størrelse – sjekk kortet/kortleseren")
        if verifiser and not _like(kilde, midlertidig):
            raise OSError(f"{navn}: innholdet i kopien er ikke likt originalen")
        os.replace(midlertidig, mal)
        shutil.copystat(kilde, mal)
    return les_sesjon(ut)


def _like(a: str, b: str) -> bool:
    with open(a, "rb") as fa, open(b, "rb") as fb:
        while True:
            x, y = fa.read(BLOKK), fb.read(BLOKK)
            if x != y:
                return False
            if not x:
                return True
