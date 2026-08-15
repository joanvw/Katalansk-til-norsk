"""AI-basert analysator som kobles på ``Analysator``-protokollen.

Følger samme mønster som resten av pakken: den nettverksavhengige delen
(kallet til språkmodellen) ligger bak en protokoll (``KIKlient``), slik at
``AIAnalysator`` kan testes uten nett med en falsk klient – på samme måte
som ``MockRDMTransport`` i ``dmx_spot_detect``.

``AnthropicKlient`` er den ekte implementasjonen. Den bruker Anthropics
offisielle Python-SDK (`pip install anthropic`) og strukturerte utdata
(`output_config.format`) slik at modellen alltid svarer med gyldig JSON på
formen ``Tilbakemelding``.
"""

from __future__ import annotations

from typing import Protocol

from .analysis import Analysator, Observasjoner
from .models import (
    CoachingØkt,
    DeltakerTilbakemelding,
    Tilbakemelding,
)
from .situations import Driver, ØnsketUtkomme

# Standardmodell. Bytt via ``AnthropicKlient(modell=...)`` ved behov.
STANDARD_MODELL = "claude-opus-5"


class KIKlient(Protocol):
    """Minimal kontrakt for en språkmodell: prompt inn, JSON ut.

    En ekte klient kaller en modell; en falsk klient i tester returnerer
    en fast ordbok. ``skjema`` er JSON-schemaet svaret skal følge.
    """

    def analyser_json(self, system: str, bruker: str, skjema: dict) -> dict:
        ...


class AnthropicKlient:
    """Ekte KI-klient mot Anthropics API via det offisielle SDK-et.

    Krever ``pip install anthropic`` og at ``ANTHROPIC_API_KEY`` er satt
    (eller en aktiv `ant auth login`-profil). SDK-et importeres først når
    klienten opprettes, slik at resten av pakken forblir avhengighetsfri.
    """

    def __init__(self, modell: str = STANDARD_MODELL, maks_tokens: int = 4096):
        import anthropic  # lokal import: kun nødvendig for ekte kjøring

        self._klient = anthropic.Anthropic()
        self.modell = modell
        self.maks_tokens = maks_tokens

    def analyser_json(self, system: str, bruker: str, skjema: dict) -> dict:
        import json

        svar = self._klient.messages.create(
            model=self.modell,
            max_tokens=self.maks_tokens,
            system=system,
            messages=[{"role": "user", "content": bruker}],
            output_config={"format": {"type": "json_schema", "schema": skjema}},
        )
        # Strukturerte utdata garanterer at første tekstblokk er gyldig JSON.
        tekst = next(b.text for b in svar.content if b.type == "text")
        return json.loads(tekst)


class AIAnalysator:
    """Analysator som lar en språkmodell tolke opptaket.

    Bygger en norsk prompt fra oppsettet og observasjonene (inkludert
    transkripsjonen), ber modellen om en tydelig, utviklende tilbakemelding
    på JSON-form, og oversetter svaret til ``Tilbakemelding``.

    ``reserve`` er en valgfri analysator (typisk ``RegelbasertAnalysator``)
    som brukes hvis KI-kallet feiler, slik at en økt aldri står uten
    tilbakemelding.
    """

    def __init__(self, klient: KIKlient, reserve: Analysator | None = None):
        self.klient = klient
        self.reserve = reserve

    def analyser(self, økt: CoachingØkt, obs: Observasjoner) -> Tilbakemelding:
        system = _SYSTEMPROMPT
        bruker = _bygg_brukerprompt(økt, obs)
        try:
            rå = self.klient.analyser_json(system, bruker, _SKJEMA)
        except Exception:
            if self.reserve is not None:
                return self.reserve.analyser(økt, obs)
            raise
        return _til_tilbakemelding(rå, økt)


# -- prompt -------------------------------------------------------------
_SYSTEMPROMPT = (
    "Du er en utviklende coach. Du analyserer et opptak fra en situasjon "
    "brukeren var i, og gir tydelig, konkret og utviklende tilbakemelding. "
    "Du er alltid klar på forbedringsområder – ikke bare det positive. "
    "Du gir også konkrete tips til hvordan brukeren bør møte hver enkelt "
    "ressurs i rommet, ut fra hvilke drivere de ser ut til å ha. "
    "Svar på norsk og kun med JSON på det angitte formatet."
)


def _bygg_brukerprompt(økt: CoachingØkt, obs: Observasjoner) -> str:
    o = økt.oppsett
    deltakere = "\n".join(
        f"  - {d.rolle} (antall {d.antall})"
        + (f", opplevd relasjon: {d.opplevd_relasjon}" if d.opplevd_relasjon else "")
        for d in o.deltakere
    )
    utkommer = ", ".join(u.value for u in o.ønskede_utkommer) or "(ingen oppgitt)"
    linjer = [
        f"Situasjon: {o.situasjon.value}",
        f"Din opplevde rolle: {o.opplevd_rolle}",
        f"Din faktiske rolle: {o.faktisk_rolle}",
        f"Agenda: {o.agenda.value}",
        f"Møtested: {o.møtested.value}"
        + (f" ({o.møtested_fritekst})" if o.møtested_fritekst else ""),
        f"Ønskede utfall: {utkommer}",
        "Ressurser i rommet:",
        deltakere or "  (ingen oppgitt)",
    ]
    if o.opplevd_relasjon:
        linjer.append(f"Din opplevde relasjon overordnet: {o.opplevd_relasjon}")
    if o.notater:
        linjer.append(f"Dine notater før treffet: {o.notater}")

    # Objektive observasjoner, hvis de finnes.
    obs_linjer = []
    if obs.min_taletid_andel is not None:
        obs_linjer.append(f"  - Din taletid: ~{round(obs.min_taletid_andel * 100)} %")
    if obs.antall_avbrytelser_fra_meg:
        obs_linjer.append(f"  - Antall avbrytelser fra deg: {obs.antall_avbrytelser_fra_meg}")
    if obs.antall_apne_sporsmal:
        obs_linjer.append(f"  - Antall åpne spørsmål fra deg: {obs.antall_apne_sporsmal}")
    for notat in obs.egne_notater:
        obs_linjer.append(f"  - Notat: {notat}")
    if obs_linjer:
        linjer.append("Objektive observasjoner:")
        linjer.extend(obs_linjer)

    linjer.append("")
    linjer.append("Transkripsjon av opptaket:")
    linjer.append(obs.transkripsjon.strip() or "(ingen transkripsjon tilgjengelig)")
    linjer.append("")
    linjer.append(
        "Gi tilbakemelding: styrker, tydelige forbedringsområder, per ressurs "
        "hvilke drivere de ser ut til å ha og hvordan dialogen med dem kan "
        "forbedres, en vurdering av hvert ønsket utfall, og forslag til neste "
        "øving."
    )
    return "\n".join(linjer)


# -- JSON-skjema (strukturerte utdata) ----------------------------------
_DRIVERVERDIER = [d.value for d in Driver]

_SKJEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "styrker": {"type": "array", "items": {"type": "string"}},
        "forbedringsområder": {"type": "array", "items": {"type": "string"}},
        "per_deltaker": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "rolle": {"type": "string"},
                    "observerte_drivere": {
                        "type": "array",
                        "items": {"type": "string", "enum": _DRIVERVERDIER},
                    },
                    "forbedring_dialog": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["rolle", "observerte_drivere", "forbedring_dialog"],
            },
        },
        "utkomme_vurdering": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "utkomme": {"type": "string"},
                    "vurdering": {"type": "string"},
                },
                "required": ["utkomme", "vurdering"],
            },
        },
        "neste_øving": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "styrker",
        "forbedringsområder",
        "per_deltaker",
        "utkomme_vurdering",
        "neste_øving",
    ],
}


# -- oversettelse JSON -> Tilbakemelding --------------------------------
_DRIVER_FRA_VERDI = {d.value: d for d in Driver}


def _til_tilbakemelding(rå: dict, økt: CoachingØkt) -> Tilbakemelding:
    per_deltaker = [
        DeltakerTilbakemelding(
            rolle=d.get("rolle", ""),
            observerte_drivere=[
                _DRIVER_FRA_VERDI[v]
                for v in d.get("observerte_drivere", [])
                if v in _DRIVER_FRA_VERDI
            ],
            forbedring_dialog=list(d.get("forbedring_dialog", [])),
        )
        for d in rå.get("per_deltaker", [])
    ]

    # Match utkomme-tekst mot de ønskede utfallene i oppsettet.
    utkomme_fra_verdi = {u.value: u for u in ØnsketUtkomme}
    utkomme_vurdering: dict[ØnsketUtkomme, str] = {}
    for post in rå.get("utkomme_vurdering", []):
        utkomme = utkomme_fra_verdi.get(post.get("utkomme", ""))
        if utkomme is not None:
            utkomme_vurdering[utkomme] = post.get("vurdering", "")

    return Tilbakemelding(
        styrker=list(rå.get("styrker", [])),
        forbedringsområder=list(rå.get("forbedringsområder", [])),
        per_deltaker=per_deltaker,
        utkomme_vurdering=utkomme_vurdering,
        neste_øving=list(rå.get("neste_øving", [])),
    )
