"""JSON ↔ domenemodell. Limet mellom HTTP-laget og ``coach``-modellen.

Holdt adskilt fra ``web`` slik at (av)serialisering kan testes for seg.
Enums (av)serialiseres på sin norske *verdi* (f.eks. «møte på jobben»),
mens valglistene til appen også tar med enum-*navnet* som stabil id.
"""

from __future__ import annotations

from enum import Enum

from .analysis import Observasjoner
from .models import (
    Deltaker,
    DeltakerTilbakemelding,
    Forberedelse,
    Lagringssted,
    Møteoppsett,
    Opptaksmodus,
    Tilbakemelding,
)
from .situations import (
    Agenda,
    Driver,
    KJENTE_ROLLER,
    Møtested,
    Situasjon,
    ØnsketUtkomme,
)


def _enum(cls, verdi, standard=None):
    """Tolk en enum fra dens verdi; gi tydelig feil ved ugyldig valg."""
    if verdi is None and standard is not None:
        return standard
    try:
        return cls(verdi)
    except ValueError as exc:
        gyldige = ", ".join(e.value for e in cls)
        raise ValueError(f"Ugyldig {cls.__name__}: {verdi!r}. Gyldige: {gyldige}") from exc


def _valg(cls) -> list[dict]:
    """Enum → liste av {id, tekst} for avkrysningsvalg i appen."""
    return [{"id": e.name, "tekst": e.value} for e in cls]


# -- inn: JSON -> modell ------------------------------------------------
def deltaker_fra_dict(d: dict) -> Deltaker:
    return Deltaker(
        rolle=str(d["rolle"]),
        antall=int(d.get("antall", 1)),
        opplevd_relasjon=str(d.get("opplevd_relasjon", "")),
        profil_id=d.get("profil_id"),
    )


def oppsett_fra_dict(d: dict) -> Møteoppsett:
    return Møteoppsett(
        situasjon=_enum(Situasjon, d["situasjon"]),
        opplevd_rolle=str(d.get("opplevd_rolle", "")),
        faktisk_rolle=str(d.get("faktisk_rolle", "")),
        deltakere=[deltaker_fra_dict(x) for x in d.get("deltakere", [])],
        agenda=_enum(Agenda, d.get("agenda"), Agenda.VANLIG_MØTE),
        møtested=_enum(Møtested, d.get("møtested"), Møtested.PÅ_JOBB),
        møtested_fritekst=str(d.get("møtested_fritekst", "")),
        opplevd_relasjon=str(d.get("opplevd_relasjon", "")),
        ønskede_utkommer=[_enum(ØnsketUtkomme, u) for u in d.get("ønskede_utkommer", [])],
        notater=str(d.get("notater", "")),
    )


def observasjoner_fra_dict(d: dict) -> Observasjoner:
    return Observasjoner(
        min_taletid_andel=d.get("min_taletid_andel"),
        antall_avbrytelser_fra_meg=int(d.get("antall_avbrytelser_fra_meg", 0)),
        antall_apne_sporsmal=int(d.get("antall_apne_sporsmal", 0)),
        taletid_per_deltaker={
            str(k): float(v) for k, v in d.get("taletid_per_deltaker", {}).items()
        },
        naadde_utkommer={
            _enum(ØnsketUtkomme, k): bool(v)
            for k, v in d.get("naadde_utkommer", {}).items()
        },
        egne_notater=[str(x) for x in d.get("egne_notater", [])],
        transkripsjon=str(d.get("transkripsjon", "")),
    )


# -- ut: modell -> JSON -------------------------------------------------
def _verdi(x):
    return x.value if isinstance(x, Enum) else x


def forberedelse_til_dict(f: Forberedelse) -> dict:
    return {
        "sannsynlige_drivere": {
            rolle: [d.value for d in drivere]
            for rolle, drivere in f.sannsynlige_drivere.items()
        },
        "møtetips": list(f.møtetips),
        "dialogtips": list(f.dialogtips),
    }


def _deltaker_tilbakemelding_til_dict(dt: DeltakerTilbakemelding) -> dict:
    return {
        "rolle": dt.rolle,
        "observerte_drivere": [d.value for d in dt.observerte_drivere],
        "forbedring_dialog": list(dt.forbedring_dialog),
    }


def tilbakemelding_til_dict(tb: Tilbakemelding) -> dict:
    return {
        "styrker": list(tb.styrker),
        "forbedringsområder": list(tb.forbedringsområder),
        "per_deltaker": [_deltaker_tilbakemelding_til_dict(dt) for dt in tb.per_deltaker],
        "utkomme_vurdering": [
            {"utkomme": u.value, "vurdering": v}
            for u, v in tb.utkomme_vurdering.items()
        ],
        "neste_øving": list(tb.neste_øving),
    }


# -- valglister til appen (før opptak) ----------------------------------
def valg_til_dict() -> dict:
    """Alle ferdigdefinerte valg appen trenger for avkrysningsskjemaet."""
    return {
        "situasjoner": _valg(Situasjon),
        "agendaer": _valg(Agenda),
        "møtesteder": _valg(Møtested),
        "ønskede_utkommer": _valg(ØnsketUtkomme),
        "roller": list(KJENTE_ROLLER),
        "drivere": _valg(Driver),
        "opptaksmodus": _valg(Opptaksmodus),
        "lagringssteder": _valg(Lagringssted),
    }
