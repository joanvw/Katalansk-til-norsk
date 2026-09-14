"""Datamodeller for medieskanningen – rene verdiobjekter uten avhengigheter."""

from __future__ import annotations

from array import array
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Hendelsestype(str, Enum):
    """Hva vi leter etter i mediefilene."""

    MENNESKE_SYNLIG = "menneske_synlig"
    MENNESKESTEMME = "menneskestemme"
    DYR_SYNLIG = "dyr_synlig"
    DYRELYD = "dyrelyd"

    @property
    def etikett(self) -> str:
        return {
            Hendelsestype.MENNESKE_SYNLIG: "mennesker i bildet",
            Hendelsestype.MENNESKESTEMME: "lyd av mennesker",
            Hendelsestype.DYR_SYNLIG: "dyr i bildet",
            Hendelsestype.DYRELYD: "lyd av dyr",
        }[self]

    @property
    def er_lyd(self) -> bool:
        return self in (Hendelsestype.MENNESKESTEMME, Hendelsestype.DYRELYD)


class Kilde(str, Enum):
    """Hvilken analyse funnet kom fra."""

    LYD = "lyd"
    BILDE = "bilde"


# Standardformater. Alt ffmpeg kan lese fungerer – dette er kun filtreringen
# vi bruker når vi går gjennom et filområde.
VIDEOFORMATER = frozenset(
    {".avi", ".mp4", ".mov", ".mkv", ".m4v", ".mpg", ".mpeg", ".webm", ".wmv", ".flv", ".mts", ".m2ts"}
)
LYDFORMATER = frozenset(
    {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wma", ".aiff", ".aif"}
)
MEDIEFORMATER = VIDEOFORMATER | LYDFORMATER


@dataclass(frozen=True)
class Mediefil:
    """Det vi trenger å vite om en fil før vi analyserer den."""

    sti: Path
    varighet: float = 0.0
    har_lyd: bool = False
    har_video: bool = False
    format: str = ""

    @property
    def navn(self) -> str:
        return self.sti.name


@dataclass
class Lydstrøm:
    """Dekodet mono-lyd, normalisert til flyttall i [-1, 1].

    ``start`` er hvor i originalfilen biten begynner, slik at lange filer kan
    leses i biter uten å holde hele lydsporet i minnet.
    """

    prøver: array
    samplerate: int
    start: float = 0.0

    @property
    def varighet(self) -> float:
        return len(self.prøver) / self.samplerate if self.samplerate else 0.0


@dataclass
class Bilderamme:
    """Ett uttrukket videobilde (kodet, typisk JPEG) med tidspunkt i filen."""

    tid: float
    data: bytes
    format: str = "jpeg"


@dataclass
class Funn:
    """Én observasjon fra en detektor, med tid relativt til det som ble analysert."""

    type: Hendelsestype
    start: float
    slutt: float
    score: float
    kilde: Kilde
    etikett: str = ""

    def forskjøvet(self, sekunder: float) -> "Funn":
        """Samme funn flyttet til absolutt tid i filen."""
        return Funn(
            type=self.type,
            start=self.start + sekunder,
            slutt=self.slutt + sekunder,
            score=self.score,
            kilde=self.kilde,
            etikett=self.etikett,
        )


@dataclass
class Sekvens:
    """En sammenhengende sekvens i én fil der noe ble funnet."""

    fil: Path
    type: Hendelsestype
    start: float
    slutt: float
    score: float = 0.0
    snittscore: float = 0.0
    antall_funn: int = 0
    kilde: Kilde = Kilde.LYD
    etiketter: dict[str, int] = field(default_factory=dict)

    @property
    def varighet(self) -> float:
        return max(0.0, self.slutt - self.start)

    @property
    def toppetiketter(self) -> list[str]:
        """Vanligste råklasser fra detektoren, mest brukt først."""
        return [navn for navn, _ in sorted(self.etiketter.items(), key=lambda p: (-p[1], p[0]))]

    def som_dict(self) -> dict:
        return {
            "fil": str(self.fil),
            "type": self.type.value,
            "beskrivelse": self.type.etikett,
            "kilde": self.kilde.value,
            "start": round(self.start, 3),
            "slutt": round(self.slutt, 3),
            "varighet": round(self.varighet, 3),
            "start_tidskode": tidskode(self.start),
            "slutt_tidskode": tidskode(self.slutt),
            "score": round(self.score, 4),
            "snittscore": round(self.snittscore, 4),
            "antall_funn": self.antall_funn,
            "etiketter": self.toppetiketter,
        }


@dataclass
class Filresultat:
    """Resultatet for én fil – sekvenser, eller en forklaring på hvorfor ikke."""

    mediefil: Mediefil
    sekvenser: list[Sekvens] = field(default_factory=list)
    feil: str = ""
    merknader: list[str] = field(default_factory=list)

    def som_dict(self) -> dict:
        return {
            "fil": str(self.mediefil.sti),
            "varighet": round(self.mediefil.varighet, 3),
            "har_lyd": self.mediefil.har_lyd,
            "har_video": self.mediefil.har_video,
            "antall_sekvenser": len(self.sekvenser),
            "feil": self.feil or None,
            "merknader": list(self.merknader),
        }


@dataclass
class Skannresultat:
    """Alt som ble funnet i filområdet."""

    rot: Path
    filer: list[Filresultat] = field(default_factory=list)

    @property
    def sekvenser(self) -> list[Sekvens]:
        alle: list[Sekvens] = []
        for filresultat in self.filer:
            alle.extend(filresultat.sekvenser)
        return alle

    def av_type(self, *typer: Hendelsestype) -> list[Sekvens]:
        ønsket = set(typer)
        return [s for s in self.sekvenser if s.type in ønsket]

    def som_dict(self) -> dict:
        sekvenser = self.sekvenser
        return {
            "rot": str(self.rot),
            "antall_filer": len(self.filer),
            "antall_sekvenser": len(sekvenser),
            "samlet_varighet": round(sum(s.varighet for s in sekvenser), 3),
            "filer": [f.som_dict() for f in self.filer],
            "sekvenser": [s.som_dict() for s in sekvenser],
        }


def tidskode(sekunder: float) -> str:
    """``HH:MM:SS.mmm`` – samme form som ffmpeg tar imot på ``-ss``."""
    sekunder = max(0.0, float(sekunder))
    timer, rest = divmod(sekunder, 3600)
    minutter, sek = divmod(rest, 60)
    return f"{int(timer):02d}:{int(minutter):02d}:{sek:06.3f}"
