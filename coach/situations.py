"""Ferdigdefinerte valg for oppsett før et opptak.

Alt her er valg brukeren huker av *før* opptaket starter. Rollene og
relasjonene er modellert som tekst (ikke enum) fordi kravet er «ferdig
definerte valg, men det skal kunne settes inn fritekst». De faste
listene ligger som konstanter (``KJENTE_ROLLER`` osv.) slik at et
grensesnitt kan vise dem som avkrysningsvalg, samtidig som et hvilket
som helst fritekst-valg er lov.
"""

from __future__ import annotations

from enum import Enum


class Situasjon(Enum):
    """Hvilken situasjon opptaket gjelder."""

    MØTE_JOBB = "møte på jobben"
    PRESENTASJON = "presentasjon"
    AKTIVITET_VENNER = "aktivitet med venner"
    DAG_FAMILIE = "dag med familien"
    AKTIVITET_KJÆRESTE = "aktivitet med kjæresten"
    PÅ_VEI_JOBB = "på vei til jobb"
    HANDLE = "ute å handle"
    VENNER_BESØK = "venner på besøk"
    JOBBFEST = "jobbfest"
    KUNDEREPRESENTASJON = "kunderepresentasjon"
    MIDDAGSSELSKAP = "middagsselskap"
    BANDØVING = "bandøving"
    TRENING = "trening"


class Agenda(Enum):
    """Hva er agendaen for treffet."""

    VANLIG_MØTE = "vanlig møte"
    DISKUSJON = "diskusjon"
    MORO = "moro"
    RELASJONSBYGGING = "relasjonsbygging"


class Møtested(Enum):
    """Hvor møtes dere. ``ANDRE_STEDER`` kan utdypes med fritekst."""

    HJEMME = "hjemme"
    PÅ_JOBB = "på jobb"
    HOS_VENNER = "hos venner"
    HOS_KUNDE = "hos kunde"
    DAGLIGE_GJØREMÅL = "under daglige gjøremål"
    NÆRMILJØ = "i nærmiljø"
    ANDRE_STEDER = "andre steder"


class ØnsketUtkomme(Enum):
    """Hva du ønsker å få ut av treffet (kan velge flere)."""

    BEDRE_VENNER = "bli bedre venner"
    BEDRE_KOLLEGAER = "bli bedre kollegaer"
    SNAKKE_UT = "få snakket ut om ting"
    DELEGERE = "delegere oppgaver til andre"
    FELLES_EIERSKAP = "et større felles eierskap"
    TETTERE_KJÆRESTE = "tettere forhold med kjæresten"
    BEDRE_KUNDE = "bedre relasjon med kunde"
    BLI_SETT = "bli sett"
    DEL_AV_GJENGEN = "være en del av gjengen"


class Driver(Enum):
    """Underliggende drivere/motivasjon hos deltakerne i rommet.

    Coachen kartlegger hvilke drivere de andre sannsynligvis har, slik at
    du kan møte dem på det som faktisk motiverer dem.
    """

    ANERKJENNELSE = "anerkjennelse"
    TILHØRIGHET = "tilhørighet"
    KONTROLL = "kontroll"
    TRYGGHET = "trygghet"
    MESTRING = "mestring"
    AUTONOMI = "autonomi"
    STATUS = "status"
    FRAMDRIFT = "framdrift"
    HARMONI = "harmoni"
    RETTFERDIGHET = "rettferdighet"
    NÆRHET = "nærhet"
    MORO = "moro"


# Ferdigdefinerte roller. Brukes både for «din opplevde rolle», «din
# faktiske rolle» og «hvem du møter». Fritekst er lov i tillegg til disse.
KJENTE_ROLLER: tuple[str, ...] = (
    "teamdeltager",
    "leder",
    "møteleder",
    "venn",
    "kjæreste",
    "foreldre",
    "barn",
    "besteforeldre",
    "tante",
    "onkel",
    "kusine",
    "fetter",
    "bestevenn",
    "bekjent",
    "gjest",
    "vert",
    "motstander",
)


def normaliser_rolle(rolle: str) -> str:
    """Trim og små bokstaver, så fritekst og faste valg kan sammenlignes."""
    return rolle.strip().lower()


def er_kjent_rolle(rolle: str) -> bool:
    """Sant hvis rollen er én av de ferdigdefinerte (ikke ren fritekst)."""
    return normaliser_rolle(rolle) in KJENTE_ROLLER
