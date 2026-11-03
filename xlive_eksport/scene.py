"""Les kanalnavn, EQ, kompressor, gate, FX og routing fra X32/M32.

Kilden er enten

* en scenefil (``.scn``) lagret fra miksebordet til USB-minnepinne
  (SETUP/USB eller ``Scenes``-knappen → *Save to USB*), eller
* tekstlinjer hentet direkte fra miksebordet over nettverk med
  ``/node``-kommandoer (se ``osc.py``) – de har nøyaktig samme format.

X32 og M32 bruker samme tekstformat, f.eks.::

    /ch/01/config "Kick" 1 RD 1
    /ch/01/preamp +0.0 OFF ON 24 80.0
    /ch/01/gate ON GATE -40.0 60.0 0 50.0 200 0
    /ch/01/dyn ON COMP RMS LOG -20.0 4.0 1 2.00 10 10.0 151 POST 0 100 OFF
    /ch/01/eq ON
    /ch/01/eq/1 PEQ 80.0 +3.00 2.0
    /ch/01/mix ON -3.0 ON +0 OFF -oo
    /config/chlink OFF ON OFF ...
    /config/routing/IN AN1-8 AN9-16 AN17-24 AN25-32 AUX/CR
    /config/routing/CARD AN1-8 AN9-16 AN17-24 AN25-32
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

_TOKEN = re.compile(r'"([^"]*)"|(\S+)')
_BLOKK = re.compile(r"^([A-Z]+?)(\d+)-(\d+)$")

# Feltnavn per kommando (rekkefølgen i X32-protokollen).
FELTER: dict[str, list[str]] = {
    "config": ["navn", "ikon", "farge", "kilde"],
    "preamp": ["trim_db", "invert", "lavkutt_pa", "lavkutt_slope", "lavkutt_hz"],
    "delay": ["pa", "ms"],
    "gate": ["pa", "modus", "terskel_db", "range_db", "attack_ms", "hold_ms",
             "release_ms", "key_kilde"],
    "gate/filter": ["pa", "type", "freq_hz"],
    "dyn": ["pa", "modus", "detektor", "envelope", "terskel_db", "ratio", "knee",
            "makeup_db", "attack_ms", "hold_ms", "release_ms", "posisjon",
            "key_kilde", "mix_pct", "auto"],
    "dyn/filter": ["pa", "type", "freq_hz"],
    "insert": ["pa", "posisjon", "fx"],
    "eq": ["pa"],
    "eq/band": ["type", "freq_hz", "gain_db", "q"],
    "mix": ["pa", "fader_db", "lr", "pan", "mono", "mono_niva_db"],
    "mix/send": ["pa", "niva_db", "pan", "type"],
    "headamp": ["gain_db", "fantom"],
}

FARGER = {
    "OFF": "#3a3a3a", "RD": "#e53935", "GN": "#43a047", "YE": "#fdd835",
    "BL": "#1e88e5", "MG": "#d81b60", "CY": "#00acc1", "WH": "#eeeeee",
}


def tokeniser(linje: str) -> list[str]:
    return [m.group(1) if m.group(1) is not None else m.group(2)
            for m in _TOKEN.finditer(linje)]


def _verdi(tekst: str) -> Any:
    if tekst == "ON":
        return True
    if tekst == "OFF":
        return False
    if tekst in ("-oo", "-inf"):
        return -math.inf
    try:
        if re.fullmatch(r"[+-]?\d+", tekst):
            return int(tekst)
        return float(tekst)
    except ValueError:
        return tekst


def _til_dict(felter: list[str], verdier: list[str]) -> dict[str, Any]:
    d: dict[str, Any] = {}
    for i, v in enumerate(verdier):
        navn = felter[i] if i < len(felter) else f"felt{i + 1}"
        d[navn] = v if navn == "navn" else _verdi(v)
    return d


@dataclass
class Kanal:
    nr: int
    navn: str = ""
    farge: str = "OFF"
    kilde: int | None = None
    preamp: dict = field(default_factory=dict)
    headamp: dict = field(default_factory=dict)
    delay: dict = field(default_factory=dict)
    gate: dict = field(default_factory=dict)
    gate_filter: dict = field(default_factory=dict)
    dyn: dict = field(default_factory=dict)
    dyn_filter: dict = field(default_factory=dict)
    insert: dict = field(default_factory=dict)
    eq_pa: bool | None = None
    eq: list[dict] = field(default_factory=list)
    mix: dict = field(default_factory=dict)
    sends: dict[int, dict] = field(default_factory=dict)

    @property
    def visningsnavn(self) -> str:
        return self.navn or f"Ch {self.nr:02d}"

    def som_dict(self) -> dict:
        return {
            "kanal": self.nr, "navn": self.navn, "farge": self.farge,
            "kilde": self.kilde, "preamp": self.preamp, "headamp": self.headamp,
            "delay": self.delay, "gate": {**self.gate, "filter": self.gate_filter},
            "kompressor": {**self.dyn, "filter": self.dyn_filter},
            "insert": self.insert, "eq": {"pa": self.eq_pa, "band": self.eq},
            "mix": self.mix,
            "sends": {f"bus{k:02d}": v for k, v in sorted(self.sends.items())},
        }


@dataclass
class Effekt:
    nr: int
    type: str = ""
    kilde: list[str] = field(default_factory=list)
    parametre: list[Any] = field(default_factory=list)

    def som_dict(self) -> dict:
        return {"fx": self.nr, "type": self.type, "kilde": self.kilde,
                "parametre": self.parametre}


@dataclass
class Spormapping:
    """Hva som ligger på ett X-Live-spor (1-basert ``spor``)."""
    spor: int
    kanal: int | None          # miksebordkanal 1–32, hvis kjent
    etikett: str               # f.eks. "Ch 05", "Out 3"


@dataclass
class Scene:
    kanaler: dict[int, Kanal] = field(default_factory=dict)
    effekter: dict[int, Effekt] = field(default_factory=dict)
    chlink: list[bool] = field(default_factory=list)       # 16 par
    routing_inn: list[str] = field(default_factory=list)
    routing_kort: list[str] = field(default_factory=list)
    headamp: dict[int, dict] = field(default_factory=dict)
    kilde: str = ""

    def kanal(self, nr: int) -> Kanal:
        if nr not in self.kanaler:
            self.kanaler[nr] = Kanal(nr)
        return self.kanaler[nr]

    def er_linket(self, kanal: int) -> bool:
        par = (kanal - 1) // 2
        return par < len(self.chlink) and self.chlink[par]

    # -- routing ----------------------------------------------------------

    def spormapping(self, antall_spor: int) -> list[Spormapping]:
        """Finn hvilken kanal hvert X-Live-spor kommer fra.

        Følger kjeden kort-utgang → inngangsblokk → kanalens kilde. Mangler
        routing i scenen, antas spor N = kanal N (vanligste oppsett).
        """
        ut: list[Spormapping] = []
        kilde_til_kanal: dict[int, int] = {}
        for k in sorted(self.kanaler.values(), key=lambda k: k.nr):
            if isinstance(k.kilde, int) and 1 <= k.kilde <= 32:
                kilde_til_kanal.setdefault(k.kilde, k.nr)
        for spor in range(1, antall_spor + 1):
            ut.append(self._map_spor(spor, kilde_til_kanal))
        return ut

    def _map_spor(self, spor: int, kilde_til_kanal: dict[int, int]) -> Spormapping:
        blokk_idx, i_blokk = divmod(spor - 1, 8)
        if blokk_idx >= len(self.routing_kort):
            nr = spor if spor <= 32 else None
            return Spormapping(spor, nr, f"Ch {spor:02d}" if nr else f"Spor {spor}")
        etikett = self.routing_kort[blokk_idx]
        inngang = None
        # Kortet tar opp samme blokk som en inngangsblokk bruker.
        if etikett in self.routing_inn[:4]:
            inngang = self.routing_inn.index(etikett) * 8 + i_blokk + 1
        else:
            # Virtual soundcheck: inngang = CARD-blokken som tilsvarer sporet.
            kort_blokk = f"CARD{blokk_idx * 8 + 1}-{blokk_idx * 8 + 8}"
            if kort_blokk in self.routing_inn[:4]:
                inngang = self.routing_inn.index(kort_blokk) * 8 + i_blokk + 1
        if inngang is not None:
            kanal = kilde_til_kanal.get(inngang)
            # Ukjent kilde (ufullstendig scene): anta standard inngang N → kanal N.
            if kanal is None and inngang <= 32 and self.kanaler.get(inngang, Kanal(0)).kilde is None:
                kanal = inngang
            if kanal is not None:
                return Spormapping(spor, kanal, f"Ch {kanal:02d}")
            return Spormapping(spor, None, f"In {inngang:02d}")
        m = _BLOKK.match(etikett)
        if m:
            prefiks, start = m.group(1), int(m.group(2))
            return Spormapping(spor, None, f"{prefiks.title()} {start + i_blokk}")
        return Spormapping(spor, None, f"{etikett} {i_blokk + 1}")

    def headamp_for_inngang(self, inngang: int) -> dict:
        blokk_idx, i_blokk = divmod(inngang - 1, 8)
        if blokk_idx >= len(self.routing_inn):
            indeks = inngang - 1               # standard: lokale innganger
        else:
            m = _BLOKK.match(self.routing_inn[blokk_idx])
            if not m:
                return {}
            basis = {"AN": 0, "A": 32, "B": 80}.get(m.group(1))
            if basis is None:
                return {}
            indeks = basis + int(m.group(2)) - 1 + i_blokk
        return self.headamp.get(indeks, {})


def les_scene_tekst(linjer: Iterable[str], kilde: str = "") -> Scene:
    scene = Scene(kilde=kilde)
    for raa in linjer:
        linje = raa.strip()
        if not linje.startswith("/"):
            continue
        tokens = tokeniser(linje)
        if not tokens:
            continue
        _tolk(scene, tokens[0], tokens[1:])
    for k in scene.kanaler.values():
        if isinstance(k.kilde, int):
            k.headamp = scene.headamp_for_inngang(k.kilde) if 1 <= k.kilde <= 32 else {}
    return scene


def les_scene_fil(sti: str) -> Scene:
    with open(sti, encoding="utf-8", errors="replace") as f:
        return les_scene_tekst(f, kilde=sti)


_CH = re.compile(r"^/ch/(\d\d)/(.+)$")


def _tolk(scene: Scene, sti: str, verdier: list[str]) -> None:
    m = _CH.match(sti)
    if m:
        kanal = scene.kanal(int(m.group(1)))
        del_ = m.group(2)
        if del_ == "config":
            d = _til_dict(FELTER["config"], verdier)
            kanal.navn = str(d.get("navn", ""))
            kanal.farge = str(d.get("farge", "OFF"))
            kanal.kilde = d.get("kilde") if isinstance(d.get("kilde"), int) else None
        elif del_ in ("preamp", "delay", "gate", "dyn", "insert", "mix"):
            setattr(kanal, del_, _til_dict(FELTER[del_], verdier))
        elif del_ == "gate/filter":
            kanal.gate_filter = _til_dict(FELTER["gate/filter"], verdier)
        elif del_ == "dyn/filter":
            kanal.dyn_filter = _til_dict(FELTER["dyn/filter"], verdier)
        elif del_ == "eq":
            kanal.eq_pa = _verdi(verdier[0]) if verdier else None
        elif re.fullmatch(r"eq/\d", del_):
            band = int(del_[3:])
            while len(kanal.eq) < band:
                kanal.eq.append({})
            kanal.eq[band - 1] = {"band": band, **_til_dict(FELTER["eq/band"], verdier)}
        elif re.fullmatch(r"mix/\d\d", del_):
            kanal.sends[int(del_[4:])] = _til_dict(FELTER["mix/send"], verdier)
        return
    if sti == "/config/chlink":
        scene.chlink = [v == "ON" for v in verdier]
    elif sti == "/config/routing/IN":
        scene.routing_inn = verdier
    elif sti == "/config/routing/CARD":
        scene.routing_kort = verdier
    elif re.fullmatch(r"/headamp/\d{3}", sti):
        scene.headamp[int(sti[9:])] = _til_dict(FELTER["headamp"], verdier)
    else:
        fx = re.fullmatch(r"/fx/(\d)(/source|/par)?", sti)
        if fx:
            e = scene.effekter.setdefault(int(fx.group(1)), Effekt(int(fx.group(1))))
            if fx.group(2) is None:
                e.type = verdier[0] if verdier else ""
            elif fx.group(2) == "/source":
                e.kilde = verdier
            else:
                e.parametre = [_verdi(v) for v in verdier]
