"""Felles «gjør alt»-funksjon for kommandolinje og GUI."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable

from . import rapport
from .eksport import (SporPlan, _mal_bits, _rens_filnavn, eksporter_sesjon,
                      planlegg_spor)
from .scene import Scene, les_scene_fil, les_scene_tekst
from .sdkort import Sesjon


@dataclass
class Valg:
    utmappe: str
    scenefil: str | None = None
    miksebord_ip: str | None = None
    bits: str | int = 24
    auto_stereo: bool = True
    stereopar: list[tuple[int, int]] = field(default_factory=list)
    monospor: set[int] = field(default_factory=set)
    navn: dict[int, str] = field(default_factory=dict)
    hopp_over: set[int] = field(default_factory=set)
    fjern_stille: bool = False
    kopier_raa: bool = False        # kopier kortets råfiler til disk først
    verifiser: bool = False         # sammenlign kopien byte for byte


def last_scene(valg: Valg, logg: Callable[[str], None] = print) -> Scene | None:
    if valg.scenefil == "auto":
        from .usb import finn_scenefiler
        filer = finn_scenefiler()
        if not filer:
            logg("Fant ingen scenefil (.scn) på USB-diskene – fortsetter uten.")
            return None
        logg(f"Bruker nyeste scenefil på USB: {filer[0]}")
        return les_scene_fil(filer[0])
    if valg.scenefil:
        logg(f"Leser scene: {valg.scenefil}")
        return les_scene_fil(valg.scenefil)
    if valg.miksebord_ip:
        from .osc import hent_fra_miksebord
        linjer = hent_fra_miksebord(valg.miksebord_ip, logg=logg)
        return les_scene_tekst(linjer, kilde=f"miksebord {valg.miksebord_ip}")
    return None


def kopier_raa(sesjon: Sesjon, valg: Valg, logg: Callable[[str], None] = print,
               fremdrift: Callable[[float, str], None] | None = None,
               nr: int = 1, antall: int = 1) -> Sesjon:
    """Kopier sesjonens råfiler til ``<målmappe>/Råfiler`` og returnér kopien."""
    from .usb import kopier_sesjon
    mal = os.path.join(valg.utmappe, "Råfiler")
    logg(f"   Kopierer råfiler til {os.path.join(mal, sesjon.id)} …")

    def fr(ferdig: int, totalt: int, fil: str) -> None:
        if fremdrift:
            fremdrift(((nr - 1) + ferdig / max(totalt, 1)) / antall,
                      f"kopierer {fil} ({ferdig / 1e9:.1f}/{totalt / 1e9:.1f} GB)")

    kopi = kopier_sesjon(sesjon, mal, fr, valg.verifiser)
    logg("   Råfiler kopiert" + (" og verifisert." if valg.verifiser else "."))
    return kopi


def sesjonsmappe(sesjon: Sesjon) -> str:
    navn = f"{sesjon.dato:%Y-%m-%d} {sesjon.navn}"
    if sesjon.navn != sesjon.id:
        navn += f" [{sesjon.id}]"
    return _rens_filnavn(navn)


def eksporter_alle(
    sesjoner: list[Sesjon],
    valg: Valg,
    logg: Callable[[str], None] = print,
    fremdrift: Callable[[float, str], None] | None = None,
) -> list[tuple[Sesjon, str, list[SporPlan]]]:
    scene = last_scene(valg, logg)
    resultat = []
    for nr, sesjon in enumerate(sesjoner, 1):
        logg(f"\n[{nr}/{len(sesjoner)}] {sesjon.beskrivelse()}")
        if valg.kopier_raa:
            sesjon = kopier_raa(sesjon, valg, logg, fremdrift, nr, len(sesjoner))
        planer = planlegg_spor(sesjon.kanaler, scene, valg.auto_stereo, valg.stereopar,
                               valg.monospor, valg.navn, valg.hopp_over)
        for p in planer:
            logg(f"   {p.filnavn:<34} {'stereo' if p.stereo else 'mono  '} "
                 f"spor {'+'.join(map(str, p.kilder)):<6} {' / '.join(p.etiketter)}")
        ut = os.path.join(valg.utmappe, sesjonsmappe(sesjon))

        def delfremdrift(andel: float, tekst: str, nr=nr) -> None:
            if fremdrift:
                fremdrift(((nr - 1) + andel) / len(sesjoner), f"{sesjon.navn}: {tekst}")

        eksporter_sesjon(sesjon, planer, ut, valg.bits, valg.fjern_stille, delfremdrift)
        bits = _mal_bits(sesjon, valg.bits)
        rapport.skriv_alt(ut, sesjon, scene, planer, bits)
        fjernet = [p.filnavn for p in planer if p.hoppet_over]
        if fjernet:
            logg(f"   Fjernet {len(fjernet)} helt stille spor: {', '.join(fjernet)}")
        logg(f"   Ferdig → {ut}")
        resultat.append((sesjon, ut, planer))
    if fremdrift:
        fremdrift(1.0, "Ferdig")
    return resultat
