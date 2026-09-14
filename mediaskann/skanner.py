"""Skanneren: gå gjennom et filområde og finn sekvensene vi er ute etter."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from .detektorer import Bildedetektor, Detektorfeil, Lyddetektor
from .media import Mediefeil, Medieleser, finn_mediefiler
from .models import (
    Filresultat,
    Funn,
    Hendelsestype,
    LYDFORMATER,
    MEDIEFORMATER,
    Mediefil,
    Skannresultat,
)
from .segmentering import Segmenteringsvalg, lag_sekvenser, utvid_punktfunn

ALLE_TYPER = frozenset(Hendelsestype)


@dataclass
class Skannvalg:
    """Hva som skal letes etter, og hvor grundig."""

    typer: frozenset[Hendelsestype] = ALLE_TYPER
    #: Hvor mange videobilder per sekund vi analyserer (1 er som regel nok).
    rammer_per_sekund: float = 1.0
    #: Lyd leses i biter av denne lengden, så lange filer ikke sprenger minnet.
    lyd_bit_sekunder: float = 300.0
    rekursivt: bool = True
    formater: frozenset[str] = frozenset(MEDIEFORMATER)
    segmentering: Segmenteringsvalg = field(default_factory=Segmenteringsvalg)

    @property
    def lydtyper(self) -> set[Hendelsestype]:
        return {t for t in self.typer if t.er_lyd}

    @property
    def bildetyper(self) -> set[Hendelsestype]:
        return {t for t in self.typer if not t.er_lyd}


class Skanner:
    """Binder sammen leser, detektorer og segmentering.

    Detektorene er valgfrie: uten lyddetektor analyseres bare bilde, og
    omvendt. Feil på én fil stopper ikke skanningen – de havner i
    ``Filresultat.feil``.
    """

    def __init__(
        self,
        leser: Medieleser,
        lyddetektor: Lyddetektor | None = None,
        bildedetektor: Bildedetektor | None = None,
        valg: Skannvalg | None = None,
        logg: Callable[[str], None] | None = None,
    ):
        self.leser = leser
        self.lyddetektor = lyddetektor
        self.bildedetektor = bildedetektor
        self.valg = valg or Skannvalg()
        self.logg = logg or (lambda melding: None)

    # -- filområde ----------------------------------------------------------
    def skann_område(self, rot: Path | str) -> Skannresultat:
        rot = Path(rot)
        filer = self._finn_filer(rot)
        self.logg(f"Fant {len(filer)} mediefil(er) i {rot}")

        resultat = Skannresultat(rot=rot)
        for nummer, sti in enumerate(filer, start=1):
            self.logg(f"[{nummer}/{len(filer)}] {sti}")
            resultat.filer.append(self.skann_fil(sti))
        return resultat

    def skann_område_iterativt(self, rot: Path | str) -> Iterable[Filresultat]:
        """Som ``skann_område``, men gir resultatet fil for fil underveis."""
        for sti in self._finn_filer(Path(rot)):
            yield self.skann_fil(sti)

    def _finn_filer(self, rot: Path) -> list[Path]:
        finn = getattr(self.leser, "finn_filer", None)
        if finn is not None:
            return list(finn(rot, rekursivt=self.valg.rekursivt, formater=self.valg.formater))
        return finn_mediefiler(rot, rekursivt=self.valg.rekursivt, formater=self.valg.formater)

    # -- én fil -------------------------------------------------------------
    def skann_fil(self, sti: Path | str) -> Filresultat:
        sti = Path(sti)
        try:
            mediefil = self.leser.les_info(sti)
        except (Mediefeil, OSError) as exc:
            tom = Mediefil(sti=sti, format=sti.suffix.lstrip("."))
            return Filresultat(mediefil=tom, feil=str(exc))

        resultat = Filresultat(mediefil=mediefil)
        funn: list[Funn] = []

        try:
            funn.extend(self._analyser_lyd(mediefil, resultat))
            funn.extend(self._analyser_bilde(mediefil, resultat))
        except (Mediefeil, Detektorfeil, OSError) as exc:
            resultat.feil = str(exc)
            return resultat

        aktuelle = [f for f in funn if f.type in self.valg.typer]
        resultat.sekvenser = lag_sekvenser(
            fil=mediefil.sti,
            funn=aktuelle,
            valg=self.valg.segmentering,
            filvarighet=mediefil.varighet,
        )
        self.logg(f"    {len(resultat.sekvenser)} sekvens(er) fra {len(aktuelle)} funn")
        return resultat

    # -- delanalyser --------------------------------------------------------
    def _analyser_lyd(self, mediefil: Mediefil, resultat: Filresultat) -> list[Funn]:
        if not self.valg.lydtyper:
            return []
        if self.lyddetektor is None:
            resultat.merknader.append("Ingen lyddetektor – hoppet over lydanalysen.")
            return []
        if not mediefil.har_lyd:
            resultat.merknader.append("Filen har ikke lydspor.")
            return []

        samplerate = getattr(self.lyddetektor, "samplerate", 16000)
        funn: list[Funn] = []
        for bit in self.leser.les_lyd(
            mediefil, samplerate=samplerate, bit_sekunder=self.valg.lyd_bit_sekunder
        ):
            funn.extend(self.lyddetektor.analyser_lyd(mediefil, bit))
        return funn

    def _analyser_bilde(self, mediefil: Mediefil, resultat: Filresultat) -> list[Funn]:
        if not self.valg.bildetyper:
            return []
        if self.bildedetektor is None:
            if mediefil.har_video:
                resultat.merknader.append("Ingen bildedetektor – hoppet over bildeanalysen.")
            return []
        if not mediefil.har_video:
            # Rene lydfiler er ikke verdt en merknad – der er det ventet.
            if mediefil.sti.suffix.lower() not in LYDFORMATER:
                resultat.merknader.append("Filen har ikke videospor.")
            return []

        rammer = self.leser.les_rammer(mediefil, per_sekund=self.valg.rammer_per_sekund)
        funn = self.bildedetektor.analyser_rammer(mediefil, rammer)
        # Ett videobilde er et punkt i tid; gi det varigheten det representerer.
        return utvid_punktfunn(funn, 1.0 / max(0.01, self.valg.rammer_per_sekund))
