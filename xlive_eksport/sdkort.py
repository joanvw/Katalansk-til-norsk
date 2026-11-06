"""Finn og les X-Live-opptak (sesjoner) på et SD-kort.

Et X-Live-kort (Behringer X32 / Midas M32) lagrer hver sesjon i en egen
mappe med et heksadesimalt navn, f.eks. ``X_LIVE/4B2C1A10/``. Mappen
inneholder:

* ``SE_LOG.BIN`` – 2048 byte sesjonslogg (kanaler, samplerate, takes,
  markører og evt. sesjonsnavn).
* ``00000001.WAV``, ``00000002.WAV`` … – én multikanals, interleavet
  WAV per ~4 GB. Filene er fortløpende og skal limes sammen.

Layout for ``SE_LOG.BIN`` (little endian, 32-bit heltall) slik den er
kartlagt av miljøet rundt X-Live (bl.a. Patrick-Gilles Maillots verktøy):

    0     sesjons-ID
    4     antall kanaler
    8     samplerate
    12    datokode
    16    antall takes (WAV-filer)
    20    antall markører
    24    total lengde
    28    take-størrelser (256 × uint32)
    1052  markører, posisjon i samples (inntil 125 × uint32)
    1552  sesjonsnavn (nullterminert tekst)

WAV-headerne er alltid fasit for format og lengde; ``SE_LOG.BIN``
brukes til markører og navn.
"""

from __future__ import annotations

import os
import re
import struct
from dataclasses import dataclass, field
from datetime import datetime

from .wav import WavFeil, WavInfo, les_wav_info

SE_LOG = "SE_LOG.BIN"
_TAKE_RE = re.compile(r"^\d{8}\.wav$", re.IGNORECASE)
_MAKS_MARKORER = 125
EGNE_MAPPER = {"X-Live eksport", "Råfiler"}


@dataclass
class SesjonsLogg:
    sesjons_id: int = 0
    kanaler: int = 0
    samplerate: int = 0
    takes: int = 0
    markorer: list[int] = field(default_factory=list)   # i samples
    navn: str = ""


def les_se_log(sti: str) -> SesjonsLogg:
    with open(sti, "rb") as f:
        data = f.read(2048)
    if len(data) < 28:
        return SesjonsLogg()
    sid, kan, sr, _dato, takes, nmark = struct.unpack("<IIIIII", data[:24])
    logg = SesjonsLogg(sid, kan, sr, takes)
    nmark = min(nmark, _MAKS_MARKORER)
    for i in range(nmark):
        off = 1052 + 4 * i
        if off + 4 > len(data):
            break
        logg.markorer.append(struct.unpack("<I", data[off:off + 4])[0])
    if len(data) > 1552:
        raa = data[1552:].split(b"\x00", 1)[0]
        try:
            tekst = raa.decode("utf-8").strip()
        except UnicodeDecodeError:
            tekst = raa.decode("latin-1").strip()
        if tekst and all(c.isprintable() for c in tekst):
            logg.navn = tekst
    return logg


@dataclass
class Sesjon:
    mappe: str
    takes: list[WavInfo]
    logg: SesjonsLogg

    @property
    def id(self) -> str:
        return os.path.basename(os.path.normpath(self.mappe))

    @property
    def navn(self) -> str:
        return self.logg.navn or self.id

    @property
    def kanaler(self) -> int:
        return self.takes[0].kanaler

    @property
    def samplerate(self) -> int:
        return self.takes[0].samplerate

    @property
    def bits(self) -> int:
        return self.takes[0].bits

    @property
    def frames(self) -> int:
        return sum(t.frames for t in self.takes)

    @property
    def varighet_s(self) -> float:
        return self.frames / self.samplerate if self.samplerate else 0.0

    @property
    def markorer(self) -> list[int]:
        return sorted(m for m in self.logg.markorer if 0 <= m <= self.frames)

    @property
    def dato(self) -> datetime:
        return datetime.fromtimestamp(os.path.getmtime(self.takes[0].sti))

    def beskrivelse(self) -> str:
        t = int(self.varighet_s)
        return (f"{self.navn}  [{self.id}]  {self.kanaler} kan, "
                f"{self.samplerate} Hz, {self.bits} bit, "
                f"{t // 3600}:{t // 60 % 60:02d}:{t % 60:02d}, "
                f"{len(self.markorer)} markører, {self.dato:%Y-%m-%d %H:%M}")


def les_sesjon(mappe: str) -> Sesjon:
    filer = sorted(f for f in os.listdir(mappe) if _TAKE_RE.match(f))
    if not filer:
        raise WavFeil(f"{mappe}: ingen opptaksfiler (00000001.WAV …)")
    takes = [les_wav_info(os.path.join(mappe, f)) for f in filer]
    forste = takes[0]
    for t in takes[1:]:
        if (t.kanaler, t.samplerate, t.bits) != (forste.kanaler, forste.samplerate, forste.bits):
            raise WavFeil(f"{t.sti}: annet format enn {forste.sti}")
    # Tomme take-filer (kortet fjernet midt i) hoppes over.
    takes = [t for t in takes if t.frames > 0] or takes[:1]
    logg_sti = _finn_fil(mappe, SE_LOG)
    logg = les_se_log(logg_sti) if logg_sti else SesjonsLogg()
    return Sesjon(mappe, takes, logg)


def _finn_fil(mappe: str, navn: str) -> str | None:
    for f in os.listdir(mappe):
        if f.upper() == navn:
            return os.path.join(mappe, f)
    return None


def finn_sesjoner(rot: str, maks_dybde: int = 3) -> list[Sesjon]:
    """Finn alle sesjoner under ``rot`` (f.eks. SD-kortets rotmappe)."""
    funnet: list[Sesjon] = []
    rot = os.path.abspath(rot)
    basis_dybde = rot.rstrip(os.sep).count(os.sep)
    for mappe, undermapper, filer in os.walk(rot):
        if mappe.count(os.sep) - basis_dybde >= maks_dybde:
            undermapper[:] = []
        # Hopp over skjulte mapper og appens egne utmapper (eksport/sikkerhetskopi).
        undermapper[:] = sorted(d for d in undermapper
                                if not d.startswith(".") and d not in EGNE_MAPPER)
        if any(_TAKE_RE.match(f) for f in filer):
            try:
                funnet.append(les_sesjon(mappe))
            except (WavFeil, OSError) as e:
                print(f"Hopper over {mappe}: {e}")
    return funnet
