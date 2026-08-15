"""Forberedelse: kartlegg sannsynlige drivere og gi råd før treffet.

Dette er en regelbasert kunnskapsbase (ren logikk, ingen nett/AI), på
samme måte som resten av pakken kjører uten eksterne avhengigheter. En
ekte AI-analysator kan kobles på via ``analysis.Analysator`` – denne
modulen gir et solid, forklarbart utgangspunkt.
"""

from __future__ import annotations

from .models import Forberedelse, Møteoppsett
from .situations import (
    Agenda,
    Driver,
    Situasjon,
    ØnsketUtkomme,
    normaliser_rolle,
)

# Hvilke drivere en rolle typisk bærer med seg inn i rommet.
_DRIVERE_PER_ROLLE: dict[str, tuple[Driver, ...]] = {
    "leder": (Driver.FRAMDRIFT, Driver.KONTROLL, Driver.STATUS, Driver.ANERKJENNELSE),
    "møteleder": (Driver.FRAMDRIFT, Driver.KONTROLL, Driver.HARMONI),
    "teamdeltager": (Driver.TILHØRIGHET, Driver.MESTRING, Driver.ANERKJENNELSE),
    "kunde": (Driver.TRYGGHET, Driver.ANERKJENNELSE, Driver.KONTROLL),
    "venn": (Driver.TILHØRIGHET, Driver.MORO, Driver.NÆRHET),
    "bestevenn": (Driver.NÆRHET, Driver.TILHØRIGHET, Driver.MORO),
    "bekjent": (Driver.TILHØRIGHET, Driver.HARMONI),
    "kjæreste": (Driver.NÆRHET, Driver.TRYGGHET, Driver.ANERKJENNELSE),
    "foreldre": (Driver.TRYGGHET, Driver.ANERKJENNELSE, Driver.NÆRHET),
    "barn": (Driver.TRYGGHET, Driver.TILHØRIGHET, Driver.AUTONOMI),
    "besteforeldre": (Driver.NÆRHET, Driver.TILHØRIGHET, Driver.ANERKJENNELSE),
    "tante": (Driver.TILHØRIGHET, Driver.NÆRHET),
    "onkel": (Driver.TILHØRIGHET, Driver.NÆRHET),
    "kusine": (Driver.TILHØRIGHET, Driver.MORO),
    "fetter": (Driver.TILHØRIGHET, Driver.MORO),
    "gjest": (Driver.HARMONI, Driver.TILHØRIGHET, Driver.TRYGGHET),
    "vert": (Driver.HARMONI, Driver.ANERKJENNELSE, Driver.TILHØRIGHET),
    "motstander": (Driver.STATUS, Driver.KONTROLL, Driver.RETTFERDIGHET),
}

# Overordnet råd for hvordan du bør møte hver situasjon.
_TIPS_PER_SITUASJON: dict[Situasjon, tuple[str, ...]] = {
    Situasjon.MØTE_JOBB: (
        "Avklar formål og ønsket beslutning i de første to minuttene.",
        "Sett av tid til at de andre får eierskap – ikke konkluder for tidlig.",
    ),
    Situasjon.PRESENTASJON: (
        "Åpne med hvorfor dette angår publikum, ikke med agendaen din.",
        "Planlegg tre pausepunkter der du sjekker at du fortsatt har rommet.",
    ),
    Situasjon.AKTIVITET_VENNER: (
        "Legg vekk «nytteformål» – tilstedeværelse er poenget.",
        "Still en åpen oppfølging på noe hver enkelt nevnte sist.",
    ),
    Situasjon.DAG_FAMILIE: (
        "Møt tempoet til den yngste/eldste, ikke ditt eget.",
        "Unngå å løse – lytt ferdig før du foreslår noe.",
    ),
    Situasjon.AKTIVITET_KJÆRESTE: (
        "Vær til stede uten skjerm; små signaler betyr mest her.",
        "Del noe om deg selv før du spør – gjensidighet skaper nærhet.",
    ),
    Situasjon.PÅ_VEI_JOBB: (
        "Bruk turen til én bevisst intensjon for dagen.",
    ),
    Situasjon.HANDLE: (
        "Korte, vennlige signaler til folk rundt deg senker eget stressnivå.",
    ),
    Situasjon.VENNER_BESØK: (
        "Som vert: senk terskelen ved å gi folk en liten oppgave.",
        "Sørg for at den stilleste også blir spurt direkte.",
    ),
    Situasjon.JOBBFEST: (
        "Bland det profesjonelle og det personlige bevisst – vær nysgjerrig, ikke taktisk.",
        "Hold én-til-én-samtaler korte nok til at flere slipper til.",
    ),
    Situasjon.KUNDEREPRESENTASJON: (
        "Bygg trygghet før du bygger sak: vis at du har forstått deres situasjon.",
        "Snakk mindre enn kunden; oppsummer det du hører for å vise at du lytter.",
    ),
    Situasjon.MIDDAGSSELSKAP: (
        "Løft samtalen til bordet, ikke bare til sidemannen.",
        "Still spørsmål som lar folk fortelle en historie, ikke svare ja/nei.",
    ),
    Situasjon.BANDØVING: (
        "Skill tydelig mellom å øve og å evaluere – ikke gjør begge samtidig.",
        "Gi konkret ros på det som funker før du foreslår endring.",
    ),
    Situasjon.TRENING: (
        "Match energien til gruppa før du prøver å heve den.",
    ),
}

_TIPS_PER_AGENDA: dict[Agenda, tuple[str, ...]] = {
    Agenda.VANLIG_MØTE: ("Ha ett tydelig ønsket utfall du kan styre mot.",),
    Agenda.DISKUSJON: (
        "Skille sak og person: gjenta motpartens poeng før du svarer.",
        "Let etter det dere er enige om før dere borer i uenigheten.",
    ),
    Agenda.MORO: ("Ikke overstyr – la det være lett; kutt egne «agendaer».",),
    Agenda.RELASJONSBYGGING: (
        "Mål: at den andre føler seg sett. Still ett spørsmål ekstra.",
    ),
}

_DIALOGTIPS_PER_UTKOMME: dict[ØnsketUtkomme, tuple[str, ...]] = {
    ØnsketUtkomme.BEDRE_VENNER: ("Del noe personlig først; be om deres side etterpå.",),
    ØnsketUtkomme.BEDRE_KOLLEGAER: ("Anerkjenn bidraget deres konkret og offentlig.",),
    ØnsketUtkomme.SNAKKE_UT: (
        "Start mykt: «Jeg vil forstå hvordan du opplevde …» – ikke med anklage.",
    ),
    ØnsketUtkomme.DELEGERE: (
        "Delegér utfall og eierskap, ikke bare oppgaver – og spør hva de trenger.",
    ),
    ØnsketUtkomme.FELLES_EIERSKAP: (
        "La de andre forme løsningen; still spørsmål framfor å presentere fasit.",
    ),
    ØnsketUtkomme.TETTERE_KJÆRESTE: ("Speil følelsen før du løser problemet.",),
    ØnsketUtkomme.BEDRE_KUNDE: ("Oppsummer kundens behov med deres egne ord.",),
    ØnsketUtkomme.BLI_SETT: (
        "Bidra med noe konkret tidlig, og be eksplisitt om innspill på det.",
    ),
    ØnsketUtkomme.DEL_AV_GJENGEN: ("Følg gruppas tempo og humor før du setter ditt preg.",),
}


def kartlegg_drivere(oppsett: Møteoppsett) -> dict[str, list[Driver]]:
    """Gjett sannsynlige drivere for hver ressurs i rommet ut fra rollen."""
    resultat: dict[str, list[Driver]] = {}
    for deltaker in oppsett.deltakere:
        nøkkel = normaliser_rolle(deltaker.rolle)
        drivere = list(_DRIVERE_PER_ROLLE.get(nøkkel, ()))
        if not drivere:
            # Ukjent/fritekst-rolle: gi et nøytralt, trygt utgangspunkt.
            drivere = [Driver.TRYGGHET, Driver.ANERKJENNELSE]
        resultat[deltaker.rolle] = drivere
    return resultat


def forbered(oppsett: Møteoppsett) -> Forberedelse:
    """Lag en komplett forberedelse for oppsettet.

    Returnerer sannsynlige drivere per deltaker, generelle møtetips for
    situasjonen/agendaen, og dialogtips som er rettet mot de ønskede
    utfallene dine.
    """
    møtetips: list[str] = []
    møtetips.extend(_TIPS_PER_SITUASJON.get(oppsett.situasjon, ()))
    møtetips.extend(_TIPS_PER_AGENDA.get(oppsett.agenda, ()))

    dialogtips: list[str] = []
    for utkomme in oppsett.ønskede_utkommer:
        dialogtips.extend(_DIALOGTIPS_PER_UTKOMME.get(utkomme, ()))

    drivere = kartlegg_drivere(oppsett)

    # Ett samlende råd basert på det dominerende driverbildet i rommet.
    alle = [d for liste in drivere.values() for d in liste]
    if alle:
        dominerende = max(set(alle), key=alle.count)
        møtetips.append(_RÅD_PER_DRIVER.get(dominerende, ""))

    return Forberedelse(
        sannsynlige_drivere=drivere,
        møtetips=[t for t in møtetips if t],
        dialogtips=[t for t in dialogtips if t],
    )


_RÅD_PER_DRIVER: dict[Driver, str] = {
    Driver.ANERKJENNELSE: "Rommet drives av anerkjennelse – se bidrag konkret og tidlig.",
    Driver.TILHØRIGHET: "Rommet drives av tilhørighet – inkludér alle før du styrer.",
    Driver.KONTROLL: "Rommet drives av kontroll – vær forutsigbar og hold rammene tydelige.",
    Driver.TRYGGHET: "Rommet drives av trygghet – bygg tillit før du utfordrer.",
    Driver.MESTRING: "Rommet drives av mestring – gi rom for at folk får vise hva de kan.",
    Driver.AUTONOMI: "Rommet drives av autonomi – gi valg framfor pålegg.",
    Driver.STATUS: "Rommet drives av status – anerkjenn posisjon uten å konkurrere.",
    Driver.FRAMDRIFT: "Rommet drives av framdrift – vis retning og hold tempo.",
    Driver.HARMONI: "Rommet drives av harmoni – demp konflikt, søk felles grunn.",
    Driver.RETTFERDIGHET: "Rommet drives av rettferdighet – vær åpen om kriterier og prosess.",
    Driver.NÆRHET: "Rommet drives av nærhet – vær personlig til stede, ikke effektiv.",
    Driver.MORO: "Rommet drives av moro – hold det lett før du blir seriøs.",
}
