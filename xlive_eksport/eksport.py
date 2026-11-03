"""Del opp X-Live-sesjoner i navngitte mono-/stereospor klare for DAW.

Flyt per sesjon:

1. ``planlegg_spor`` bestemmer navn og mono/stereo for hvert spor ut fra
   scenen (kanalnavn, kanal-link, kort-routing) og evt. overstyringer.
2. ``eksporter_sesjon`` leser alle takes (``00000001.WAV`` …) i ett
   strøk, deler ut kanalene og skriver én WAV per spor. Alle filer
   starter på sample 0 og er like lange, så de ligger synkront når de
   dras inn i en DAW.
3. ``rapport`` skriver markører, sporliste, innstillingsark og
   DAW-prosjekt ved siden av lydfilene.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Callable

from .scene import Kanal, Scene, Spormapping
from .sdkort import Sesjon
from .wav import (WAVE_FORMAT_IEEE_FLOAT, Markor, WavSkriver, del_ut_kanaler,
                  er_digital_stillhet)

FRAMES_PER_BLOKK = 32768

Fremdrift = Callable[[float, str], None]


@dataclass
class SporPlan:
    nr: int                         # rekkefølge i eksporten (1 …)
    navn: str
    kilder: list[int]               # X-Live-spor, 1-basert (1 eller 2 stk.)
    kanaler: list[Kanal | None] = field(default_factory=list)
    etiketter: list[str] = field(default_factory=list)
    filnavn: str = ""
    stille: bool = True
    hoppet_over: bool = False

    @property
    def stereo(self) -> bool:
        return len(self.kilder) == 2


def _rens_filnavn(navn: str) -> str:
    navn = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", navn).strip(" .")
    return navn or "spor"


_LR = re.compile(r"[\s_\-]*(\(?\b(L|R|V|H|Left|Right|Venstre|Høyre)\b\)?)$", re.IGNORECASE)


def stereo_navn(a: str, b: str) -> str:
    ra, rb = _LR.sub("", a).strip(), _LR.sub("", b).strip()
    if ra and ra.lower() == rb.lower():
        return ra
    if a == b:
        return a
    return f"{a} + {b}"


def parse_par(tekst: str) -> list[tuple[int, int]]:
    """``"31-32, 15-16"`` → ``[(31, 32), (15, 16)]``."""
    par = []
    for del_ in re.split(r"[,\s]+", tekst.strip()):
        if not del_:
            continue
        m = re.fullmatch(r"(\d+)[-/+](\d+)", del_)
        if not m:
            raise ValueError(f"Ugyldig stereopar: {del_!r} (bruk f.eks. 31-32)")
        a, b = int(m.group(1)), int(m.group(2))
        if b != a + 1:
            raise ValueError(f"Stereopar må være naboer: {del_!r}")
        par.append((a, b))
    return par


def parse_tallsett(tekst: str | None) -> set[int]:
    """``"1-4, 9"`` → ``{1, 2, 3, 4, 9}``."""
    ut: set[int] = set()
    for del_ in (tekst or "").replace(" ", "").split(","):
        if not del_:
            continue
        if "-" in del_:
            a, b = map(int, del_.split("-", 1))
            ut.update(range(a, b + 1))
        else:
            ut.add(int(del_))
    return ut


def parse_navnefil(sti: str) -> dict[int, str]:
    """Les en enkel tekst/CSV-fil: ``spornummer;navn`` (eller komma/tab)."""
    navn: dict[int, str] = {}
    with open(sti, encoding="utf-8-sig") as f:
        for linje in f:
            linje = linje.strip()
            if not linje or linje.startswith("#"):
                continue
            deler = re.split(r"[;,\t]", linje, maxsplit=1)
            if len(deler) == 2 and deler[0].strip().isdigit():
                navn[int(deler[0])] = deler[1].strip()
    return navn


def planlegg_spor(
    antall_spor: int,
    scene: Scene | None = None,
    auto_stereo: bool = True,
    stereopar: list[tuple[int, int]] | None = None,
    monospor: set[int] | None = None,
    navn: dict[int, str] | None = None,
    hopp_over: set[int] | None = None,
) -> list[SporPlan]:
    navn = navn or {}
    hopp_over = hopp_over or set()
    monospor = monospor or set()
    if scene is not None:
        mapping = scene.spormapping(antall_spor)
    else:
        mapping = [Spormapping(s, None, f"Spor {s:02d}") for s in range(1, antall_spor + 1)]

    def kanal_for(m: Spormapping) -> Kanal | None:
        if scene is None or m.kanal is None:
            return None
        return scene.kanaler.get(m.kanal)

    def navn_for(m: Spormapping) -> str:
        if m.spor in navn:
            return navn[m.spor]
        k = kanal_for(m)
        if k is not None and k.navn:
            return k.navn
        return m.etikett

    par: set[int] = set()        # første spor i hvert stereopar
    for a, b in stereopar or []:
        if 1 <= a < b <= antall_spor:
            par.add(a)
    if auto_stereo and scene is not None:
        for m in mapping[:-1]:
            neste = mapping[m.spor]
            if (m.kanal and neste.kanal == m.kanal + 1 and m.kanal % 2 == 1
                    and scene.er_linket(m.kanal)):
                par.add(m.spor)
    par = {p for p in par if p not in monospor and p + 1 not in monospor}

    planer: list[SporPlan] = []
    spor = 1
    while spor <= antall_spor:
        m = mapping[spor - 1]
        if spor in par and spor + 1 <= antall_spor:
            m2 = mapping[spor]
            kilder = [spor, spor + 1]
            sporets_navn = navn.get(spor) if spor in navn else stereo_navn(navn_for(m), navn_for(m2))
            plan = SporPlan(0, sporets_navn, kilder, [kanal_for(m), kanal_for(m2)],
                            [m.etikett, m2.etikett])
            spor += 2
        else:
            plan = SporPlan(0, navn_for(m), [spor], [kanal_for(m)], [m.etikett])
            spor += 1
        if any(k in hopp_over for k in plan.kilder):
            continue
        planer.append(plan)

    brukt: set[str] = set()
    for i, p in enumerate(planer, 1):
        p.nr = i
        grunn = f"{i:02d} {_rens_filnavn(p.navn)}"
        kandidat, n = grunn, 2
        while kandidat.lower() in brukt:
            kandidat = f"{grunn} ({n})"
            n += 1
        brukt.add(kandidat.lower())
        p.filnavn = kandidat + ".wav"
    return planer


def _mal_bits(sesjon: Sesjon, bits: str | int) -> int:
    if sesjon.takes[0].formattag == WAVE_FORMAT_IEEE_FLOAT:
        return sesjon.bits
    if bits in ("samme", "same", None):
        return sesjon.bits
    return min(int(bits), sesjon.bits)


def eksporter_sesjon(
    sesjon: Sesjon,
    planer: list[SporPlan],
    utmappe: str,
    bits: str | int = 24,
    fjern_stille: bool = False,
    fremdrift: Fremdrift | None = None,
) -> list[SporPlan]:
    os.makedirs(utmappe, exist_ok=True)
    mal = _mal_bits(sesjon, bits)
    mal_bps = mal // 8
    kilde_bps = sesjon.bits // 8
    n_kan = sesjon.kanaler
    for p in planer:
        if max(p.kilder) > n_kan:
            raise ValueError(f"{p.filnavn}: sesjonen har bare {n_kan} spor")

    skrivere = [WavSkriver(os.path.join(utmappe, p.filnavn), len(p.kilder),
                           sesjon.samplerate, mal, sesjon.takes[0].formattag)
                for p in planer]
    totalt = max(sesjon.frames, 1)
    ferdig = 0
    try:
        for take in sesjon.takes:
            blokk = FRAMES_PER_BLOKK * take.frame_storrelse
            igjen = take.data_lengde
            with open(take.sti, "rb") as f:
                f.seek(take.data_start)
                while igjen > 0:
                    data = f.read(min(blokk, igjen))
                    if not data:
                        break
                    data = data[:len(data) - len(data) % take.frame_storrelse]
                    if not data:
                        break
                    igjen -= len(data)
                    for p, s in zip(planer, skrivere):
                        biter = del_ut_kanaler(data, n_kan, kilde_bps,
                                               [k - 1 for k in p.kilder], mal_bps)
                        if p.stille and not er_digital_stillhet(biter):
                            p.stille = False
                        s.skriv(biter)
                    ferdig += len(data) // take.frame_storrelse
                    if fremdrift:
                        fremdrift(ferdig / totalt, os.path.basename(take.sti))
        for s in skrivere:
            s.markorer = [Markor(m, f"Markør {i}") for i, m in enumerate(sesjon.markorer, 1)]
    finally:
        for s in skrivere:
            s.lukk()

    if fjern_stille:
        for p in planer:
            if p.stille:
                os.remove(os.path.join(utmappe, p.filnavn))
                p.hoppet_over = True
    return planer
