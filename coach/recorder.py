"""Opptak av lyd/bilde og lagring – abstrahert bak protokoller.

Etter samme mønster som ``dmx_spot_detect.transport``: kjernelogikken er
ren og testbar, mens den maskinvare-/plattformavhengige delen ligger bak
en protokoll. En mobilapp implementerer ``Opptaker`` mot kameraet/mikken
og ``Lagringsmål`` mot mobilens fillager eller en valgt skytjeneste –
uten å endre noe annet i pakken.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from .models import (
    Lagringssted,
    Opptak,
    Opptaksmodus,
    Opptaksstatus,
)


@runtime_checkable
class Lagringsmål(Protocol):
    """Hvor mediet faktisk havner (mobil, lokal disk, sky …)."""

    sted: Lagringssted

    def lagre(self, data: bytes, filnavn: str) -> str:
        """Lagre ``data`` og returnér en referanse (filsti/URL/nøkkel)."""
        ...


@runtime_checkable
class Opptaker(Protocol):
    """Kilde for lyd/bilde. Én i mobilappen, én mock i testene."""

    def start(self, modus: Opptaksmodus) -> None:
        ...

    def stopp(self) -> bytes:
        """Stopp og returnér de rå mediedataene."""
        ...


class LokalLagring:
    """Skriver opptak til en katalog på disk (også brukbart på mobil).

    Brukes for ``MOBIL`` og ``LOKAL_DISK``: en mobilapp peker bare
    ``katalog`` til appens dokumentområde på telefonen.
    """

    def __init__(self, katalog: str | Path, sted: Lagringssted = Lagringssted.LOKAL_DISK):
        self.katalog = Path(katalog)
        self.katalog.mkdir(parents=True, exist_ok=True)
        self.sted = sted

    def lagre(self, data: bytes, filnavn: str) -> str:
        sti = self.katalog / filnavn
        sti.write_bytes(data)
        return str(sti)


class MinneLagring:
    """Lagringsmål i minnet – for tester og demo, uten å røre disk/nett."""

    def __init__(self, sted: Lagringssted = Lagringssted.MOBIL):
        self.sted = sted
        self.filer: dict[str, bytes] = {}

    def lagre(self, data: bytes, filnavn: str) -> str:
        self.filer[filnavn] = data
        return f"minne://{filnavn}"


class MockOpptaker:
    """Simulerer et opptak uten maskinvare (returnerer plassholderbytes)."""

    def __init__(self, innhold: bytes = b"MOCK-MEDIA"):
        self._innhold = innhold
        self._aktiv = False

    def start(self, modus: Opptaksmodus) -> None:
        self._aktiv = True

    def stopp(self) -> bytes:
        self._aktiv = False
        return self._innhold


class Opptaksøkt:
    """Styrer ett opptak fra start til lagret fil.

    Oppdaterer et ``Opptak``-objekt underveis, slik at resten av økta har
    korrekt status, tidsstempler og lagringsreferanse.
    """

    def __init__(self, opptaker: Opptaker, lagringsmål: Lagringsmål):
        self.opptaker = opptaker
        self.lagringsmål = lagringsmål

    def start(self, opptak: Opptak) -> Opptak:
        if opptak.status == Opptaksstatus.TAR_OPP:
            raise RuntimeError("Opptaket er allerede i gang.")
        opptak.lagringssted = self.lagringsmål.sted
        opptak.startet = datetime.now()
        opptak.status = Opptaksstatus.TAR_OPP
        self.opptaker.start(opptak.modus)
        return opptak

    def stopp(self, opptak: Opptak, filnavn: str | None = None) -> Opptak:
        if opptak.status != Opptaksstatus.TAR_OPP:
            raise RuntimeError("Det er ikke noe pågående opptak å stoppe.")
        data = self.opptaker.stopp()
        opptak.stoppet = datetime.now()
        navn = filnavn or _standard_filnavn(opptak.modus, opptak.startet)
        opptak.referanse = self.lagringsmål.lagre(data, navn)
        opptak.status = Opptaksstatus.FERDIG
        return opptak


def _standard_filnavn(modus: Opptaksmodus, startet: datetime | None) -> str:
    stempel = (startet or datetime.now()).strftime("%Y%m%d-%H%M%S")
    endelse = "m4a" if modus == Opptaksmodus.LYD else "mp4"
    return f"coaching-{stempel}.{endelse}"
