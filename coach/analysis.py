"""Analyse i etterkant: tydelig, utviklende tilbakemelding.

``Analysator`` er en protokoll slik at en ekte AI-analysator (som tolker
transkripsjon/video) kan kobles på senere. ``RegelbasertAnalysator`` gir
en forklarbar, avhengighetsfri analyse ut fra oppsett + en enkel
observasjonsstruktur du (eller et transkripsjonstrinn) fyller ut.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .models import (
    CoachingØkt,
    DeltakerTilbakemelding,
    Tilbakemelding,
)
from .preparation import kartlegg_drivere
from .situations import Driver, ØnsketUtkomme, normaliser_rolle


@dataclass
class Observasjoner:
    """Enkle, målbare observasjoner fra opptaket.

    Dette er bevisst grovkornet slik at det kan fylles ut manuelt, av en
    transkripsjonsmotor, eller av en AI. Alt er valgfritt.
    """

    min_taletid_andel: float | None = None  # 0.0–1.0
    antall_avbrytelser_fra_meg: int = 0
    antall_apne_sporsmal: int = 0
    # rolle -> hvor mye vedkommende slapp til (0.0–1.0)
    taletid_per_deltaker: dict[str, float] = field(default_factory=dict)
    # ønsket utkomme -> ble det nådd?
    naadde_utkommer: dict[ØnsketUtkomme, bool] = field(default_factory=dict)
    egne_notater: list[str] = field(default_factory=list)


class Analysator(Protocol):
    def analyser(self, økt: CoachingØkt, obs: Observasjoner) -> Tilbakemelding:
        ...


class RegelbasertAnalysator:
    """Regelbasert coach: peker tydelig på forbedringsområder.

    Prinsippet er utvikling – analysen anerkjenner det som fungerer, men
    er alltid konkret på hva neste steg bør være.
    """

    def analyser(self, økt: CoachingØkt, obs: Observasjoner) -> Tilbakemelding:
        tb = Tilbakemelding()
        oppsett = økt.oppsett

        self._vurder_taletid(obs, tb)
        self._vurder_lytting(obs, tb)
        self._vurder_deltakere(økt, obs, tb)
        self._vurder_utkommer(oppsett, obs, tb)

        if not tb.styrker:
            tb.styrker.append("Du gjennomførte og tok opp økta – grunnlaget for å øve er på plass.")
        if not tb.neste_øving:
            tb.neste_øving.append("Velg ett forbedringsområde over og øv bevisst på det neste gang.")
        return tb

    # -- delvurderinger --------------------------------------------------
    def _vurder_taletid(self, obs: Observasjoner, tb: Tilbakemelding) -> None:
        andel = obs.min_taletid_andel
        if andel is None:
            return
        if andel > 0.6:
            tb.forbedringsområder.append(
                f"Du snakket ~{round(andel * 100)} % av tiden. Sikt mot at de andre "
                "får minst like mye plass – still, og hold ut stillheten etterpå."
            )
            tb.neste_øving.append("Øv på å stille et spørsmål og telle til tre før du fyller pausen.")
        elif andel < 0.25:
            tb.styrker.append("Du ga de andre god plass til å snakke.")
            tb.forbedringsområder.append(
                "Du var svært tilbaketrukket – ta tydeligere eierskap til minst ett poeng."
            )
        else:
            tb.styrker.append("God balanse mellom å snakke selv og slippe andre til.")

    def _vurder_lytting(self, obs: Observasjoner, tb: Tilbakemelding) -> None:
        if obs.antall_avbrytelser_fra_meg >= 3:
            tb.forbedringsområder.append(
                f"Du avbrøt {obs.antall_avbrytelser_fra_meg} ganger – la folk fullføre "
                "tanken før du svarer."
            )
        elif obs.antall_avbrytelser_fra_meg == 0:
            tb.styrker.append("Du lot folk snakke ferdig uten å avbryte.")

        if obs.antall_apne_sporsmal >= 3:
            tb.styrker.append(
                f"Du brukte {obs.antall_apne_sporsmal} åpne spørsmål – det inviterer folk inn."
            )
        elif obs.antall_apne_sporsmal == 0:
            tb.forbedringsområder.append(
                "Ingen åpne spørsmål registrert – prøv «hvordan …» / «hva tenker du om …»."
            )

    def _vurder_deltakere(
        self, økt: CoachingØkt, obs: Observasjoner, tb: Tilbakemelding
    ) -> None:
        drivere = kartlegg_drivere(økt.oppsett)
        for deltaker in økt.oppsett.deltakere:
            dt = DeltakerTilbakemelding(
                rolle=deltaker.rolle,
                observerte_drivere=drivere.get(deltaker.rolle, []),
            )
            andel = _slaa_opp_taletid(obs.taletid_per_deltaker, deltaker.rolle)
            if andel is not None and andel < 0.15:
                dt.forbedring_dialog.append(
                    "Slapp lite til – spør denne personen direkte og med navn neste gang."
                )
            for driver in dt.observerte_drivere:
                råd = _DIALOG_PER_DRIVER.get(driver)
                if råd:
                    dt.forbedring_dialog.append(råd)
            # unngå duplikater, behold rekkefølge
            dt.forbedring_dialog = list(dict.fromkeys(dt.forbedring_dialog))
            tb.per_deltaker.append(dt)

    def _vurder_utkommer(self, oppsett, obs: Observasjoner, tb: Tilbakemelding) -> None:
        for utkomme in oppsett.ønskede_utkommer:
            nådd = obs.naadde_utkommer.get(utkomme)
            if nådd is True:
                tb.utkomme_vurdering[utkomme] = "Oppnådd – gjenta det som funket."
                tb.styrker.append(f"Du nådde målet «{utkomme.value}».")
            elif nådd is False:
                tb.utkomme_vurdering[utkomme] = "Ikke oppnådd ennå."
                tb.forbedringsområder.append(
                    f"Målet «{utkomme.value}» ble ikke nådd – planlegg ett konkret grep for det neste gang."
                )
            else:
                tb.utkomme_vurdering[utkomme] = "Usikkert – noter et tegn du kan måle det på."


def _slaa_opp_taletid(kart: dict[str, float], rolle: str) -> float | None:
    mål = normaliser_rolle(rolle)
    for k, v in kart.items():
        if normaliser_rolle(k) == mål:
            return v
    return None


_DIALOG_PER_DRIVER: dict[Driver, str] = {
    Driver.ANERKJENNELSE: "Anerkjenn bidraget deres eksplisitt – de trenger å bli sett.",
    Driver.TILHØRIGHET: "Knytt poengene til «vi/oss» framfor «jeg».",
    Driver.KONTROLL: "Gi forutsigbarhet: si hva som skjer og når.",
    Driver.TRYGGHET: "Senk tempoet og bekreft før du utfordrer.",
    Driver.MESTRING: "Gi dem et konkret felt der de får vise kompetanse.",
    Driver.AUTONOMI: "Tilby valg framfor instruks.",
    Driver.STATUS: "Anerkjenn posisjonen deres uten å gå i konkurranse.",
    Driver.FRAMDRIFT: "Vær kort og vis retning – de vil videre.",
    Driver.HARMONI: "Adressér uenighet varsomt; søk felles grunn først.",
    Driver.RETTFERDIGHET: "Vær åpen om kriterier og begrunn beslutninger.",
    Driver.NÆRHET: "Vær personlig og til stede, ikke oppgaveorientert.",
    Driver.MORO: "Hold tonen lett før du blir alvorlig.",
}
