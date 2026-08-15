"""Coachen – limet mellom oppsett, opptak, profilarkiv og analyse.

Typisk flyt:

    coach = Coach(opptaker, lagringsmål, arkiv)
    økt = coach.ny_økt(oppsett)          # forbereder + kobler profiler
    coach.start_opptak(økt)              # aktiver opptak i situasjonen
    ...                                  # møtet skjer
    coach.stopp_opptak(økt)             # lagre på mobil/valgt plattform
    tb = coach.analyser(økt, observasjoner)   # gå igjennom sammen etterpå
"""

from __future__ import annotations

from .analysis import Analysator, Observasjoner, RegelbasertAnalysator
from .models import (
    CoachingØkt,
    Møteoppsett,
    Opptak,
    Tilbakemelding,
)
from .preparation import forbered
from .profiles import ProfilArkiv
from .recorder import Opptaksøkt, Opptaker, Lagringsmål


class Coach:
    """Coachende agent som kjører hele løpet rundt en økt."""

    def __init__(
        self,
        opptaker: Opptaker,
        lagringsmål: Lagringsmål,
        arkiv: ProfilArkiv | None = None,
        analysator: Analysator | None = None,
    ):
        self._opptaksøkt = Opptaksøkt(opptaker, lagringsmål)
        self.arkiv = arkiv
        self.analysator = analysator or RegelbasertAnalysator()

    # -- før treffet -----------------------------------------------------
    def ny_økt(self, oppsett: Møteoppsett, opptak: Opptak | None = None) -> CoachingØkt:
        """Opprett en økt, kjør forberedelse og koble på anonyme profiler."""
        økt = CoachingØkt(oppsett=oppsett, opptak=opptak or Opptak())
        økt.forberedelse = forbered(oppsett)
        if self.arkiv:
            self._koble_profiler(oppsett)
        return økt

    def _koble_profiler(self, oppsett: Møteoppsett) -> None:
        assert self.arkiv is not None
        for deltaker in oppsett.deltakere:
            # Bruk opplevd relasjon som privat kallenavn hvis oppgitt, ellers rollen.
            kallenavn = deltaker.opplevd_relasjon or f"{deltaker.rolle}-{oppsett.situasjon.name}"
            profil = self.arkiv.hent_eller_opprett(kallenavn, deltaker.rolle)
            deltaker.profil_id = profil.profil_id

    # -- under treffet ---------------------------------------------------
    def start_opptak(self, økt: CoachingØkt) -> Opptak:
        return self._opptaksøkt.start(økt.opptak)

    def stopp_opptak(self, økt: CoachingØkt, filnavn: str | None = None) -> Opptak:
        return self._opptaksøkt.stopp(økt.opptak, filnavn)

    # -- etter treffet ---------------------------------------------------
    def analyser(
        self, økt: CoachingØkt, observasjoner: Observasjoner | None = None
    ) -> Tilbakemelding:
        """Lag tilbakemelding og skriv lærdom tilbake til profilarkivet."""
        tb = self.analysator.analyser(økt, observasjoner or Observasjoner())
        økt.tilbakemelding = tb
        if self.arkiv:
            self._oppdater_profiler(økt, tb)
        return tb

    def _oppdater_profiler(self, økt: CoachingØkt, tb: Tilbakemelding) -> None:
        assert self.arkiv is not None
        per_rolle = {dt.rolle: dt for dt in tb.per_deltaker}
        for deltaker in økt.oppsett.deltakere:
            if not deltaker.profil_id:
                continue
            dt = per_rolle.get(deltaker.rolle)
            self.arkiv.registrer_hendelse(
                deltaker.profil_id,
                hendelse=f"{økt.oppsett.situasjon.value} ({økt.opprettet:%Y-%m-%d})",
                drivere=dt.observerte_drivere if dt else None,
                håndteringstips=dt.forbedring_dialog if dt else None,
            )
        self.arkiv.lagre()
