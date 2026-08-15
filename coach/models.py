"""Dataklasser som binder oppsett, opptak, forberedelse og analyse sammen.

Modellen er ren data (ingen sideeffekter) slik at den er lett å teste,
serialisere og gjenbruke uansett grensesnitt (mobilapp, CLI, web).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .situations import (
    Agenda,
    Driver,
    Møtested,
    Situasjon,
    ØnsketUtkomme,
)


class Opptaksmodus(Enum):
    """Hva som tas opp."""

    LYD = "lyd"
    BILDE = "bilde"
    LYD_OG_BILDE = "lyd og bilde"


class Lagringssted(Enum):
    """Hvor opptaket lagres."""

    MOBIL = "mobil"
    LOKAL_DISK = "lokal disk"
    SKY = "sky"


class Opptaksstatus(Enum):
    KLAR = "klar"
    TAR_OPP = "tar opp"
    FERDIG = "ferdig"
    AVBRUTT = "avbrutt"


@dataclass
class Deltaker:
    """Én (type) person du møter, med antall.

    ``rolle`` er ferdigvalg eller fritekst. ``profil_id`` peker til en
    anonymisert profil i arkivet, slik at coachen kan huske og trene på
    håndteringen av relasjonen over tid – uten å lagre identiteten.
    """

    rolle: str
    antall: int = 1
    opplevd_relasjon: str = ""
    profil_id: str | None = None


@dataclass
class Møteoppsett:
    """Alt du huker av før opptaket starter."""

    situasjon: Situasjon
    opplevd_rolle: str
    faktisk_rolle: str
    deltakere: list[Deltaker] = field(default_factory=list)
    agenda: Agenda = Agenda.VANLIG_MØTE
    møtested: Møtested = Møtested.PÅ_JOBB
    møtested_fritekst: str = ""
    opplevd_relasjon: str = ""  # valgfri, overordnet
    ønskede_utkommer: list[ØnsketUtkomme] = field(default_factory=list)
    notater: str = ""

    @property
    def antall_personer(self) -> int:
        return sum(d.antall for d in self.deltakere)


@dataclass
class Opptak:
    """Metadata om selve opptaket (ikke mediedataene i seg selv)."""

    modus: Opptaksmodus = Opptaksmodus.LYD
    lagringssted: Lagringssted = Lagringssted.MOBIL
    status: Opptaksstatus = Opptaksstatus.KLAR
    startet: datetime | None = None
    stoppet: datetime | None = None
    referanse: str = ""  # filsti / URL / objektnøkkel hos lagringsmålet

    @property
    def varighet_sekunder(self) -> float | None:
        if self.startet and self.stoppet:
            return (self.stoppet - self.startet).total_seconds()
        return None


@dataclass
class Forberedelse:
    """Coachens råd *før* du går inn i situasjonen."""

    sannsynlige_drivere: dict[str, list[Driver]] = field(default_factory=dict)
    møtetips: list[str] = field(default_factory=list)
    dialogtips: list[str] = field(default_factory=list)


@dataclass
class DeltakerTilbakemelding:
    """Tilbakemelding på hvordan du bør møte én ressurs i rommet."""

    rolle: str
    observerte_drivere: list[Driver] = field(default_factory=list)
    forbedring_dialog: list[str] = field(default_factory=list)


@dataclass
class Tilbakemelding:
    """Coachens analyse *etter* opptaket – utviklende og tydelig."""

    styrker: list[str] = field(default_factory=list)
    forbedringsområder: list[str] = field(default_factory=list)
    per_deltaker: list[DeltakerTilbakemelding] = field(default_factory=list)
    utkomme_vurdering: dict[ØnsketUtkomme, str] = field(default_factory=dict)
    neste_øving: list[str] = field(default_factory=list)


@dataclass
class CoachingØkt:
    """En hel økt: oppsett → forberedelse → opptak → tilbakemelding."""

    oppsett: Møteoppsett
    opptak: Opptak = field(default_factory=Opptak)
    forberedelse: Forberedelse | None = None
    tilbakemelding: Tilbakemelding | None = None
    opprettet: datetime = field(default_factory=datetime.now)


@dataclass
class Profil:
    """Anonymisert profil av en person du møter over tid.

    Inneholder *ingen* identifiserende data – bare et alias, antatte
    drivere og en historikk med håndteringstips, slik at dere kan trene
    på relasjonen sammen i etterkant.
    """

    profil_id: str
    alias: str
    typisk_rolle: str = ""
    antatte_drivere: list[Driver] = field(default_factory=list)
    hendelser: list[str] = field(default_factory=list)
    håndteringstips: list[str] = field(default_factory=list)
