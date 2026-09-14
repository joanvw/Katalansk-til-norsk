"""Lesing av mediefiler – avhengigheten mot ffmpeg ligger bak en protokoll.

Samme mønster som ``dmx_spot_detect.transport``: all analyse- og
segmenteringslogikk jobber mot ``Medieleser``, slik at den kan testes med
``MockMedieleser`` uten at verken ffmpeg eller ekte filer er tilgjengelig.
"""

from __future__ import annotations

import json
import shutil
import struct
import subprocess
import tempfile
import wave
from array import array
from pathlib import Path
from typing import Iterable, Iterator, Protocol, runtime_checkable

from .models import (
    Bilderamme,
    MEDIEFORMATER,
    Lydstrøm,
    Mediefil,
    tidskode,
)

STANDARD_SAMPLERATE = 16000


class Mediefeil(Exception):
    """Feil ved lesing, dekoding eller uttrekk av en mediefil."""


@runtime_checkable
class Medieleser(Protocol):
    """Alt analysen trenger av en mediefil."""

    def finn_filer(self, rot: Path, rekursivt: bool = True, formater: Iterable[str] = MEDIEFORMATER) -> list[Path]:
        """Mediefilene i et filområde."""
        ...

    def les_info(self, sti: Path) -> Mediefil:
        """Varighet og hvilke spor filen har."""
        ...

    def les_lyd(
        self, fil: Mediefil, samplerate: int = STANDARD_SAMPLERATE, bit_sekunder: float = 300.0
    ) -> Iterator[Lydstrøm]:
        """Mono-lyd i biter, slik at lange filer ikke tas inn i minnet samlet."""
        ...

    def les_rammer(self, fil: Mediefil, per_sekund: float = 1.0) -> Iterator[Bilderamme]:
        """Videobilder med jevne mellomrom."""
        ...

    def klipp_ut(self, fil: Mediefil, start: float, slutt: float, mål: Path, nøyaktig: bool = False) -> Path:
        """Skriv sekvensen ``start``–``slutt`` til ``mål`` og returnér stien."""
        ...


def finn_mediefiler(
    rot: Path | str,
    rekursivt: bool = True,
    formater: Iterable[str] = MEDIEFORMATER,
) -> list[Path]:
    """Alle mediefiler i et filområde, sortert, uten å følge symlenker."""
    rot = Path(rot)
    if rot.is_file():
        return [rot]
    if not rot.is_dir():
        raise Mediefeil(f"Filområdet finnes ikke: {rot}")

    endelser = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in formater}
    mønster = "**/*" if rekursivt else "*"
    funnet = [
        sti
        for sti in rot.glob(mønster)
        if sti.is_file() and not sti.is_symlink() and sti.suffix.lower() in endelser
    ]
    return sorted(funnet)


def _kjør(kommando: list[str], binærutdata: bool = False) -> bytes:
    resultat = subprocess.run(kommando, capture_output=True)
    if resultat.returncode != 0:
        feilmelding = resultat.stderr.decode("utf-8", errors="replace").strip().splitlines()
        siste = feilmelding[-1] if feilmelding else "ukjent feil"
        raise Mediefeil(f"{Path(kommando[0]).name} feilet: {siste}")
    return resultat.stdout if binærutdata else resultat.stdout


class FFmpegLeser:
    """Ekte lesing via ``ffmpeg``/``ffprobe`` (eneste eksterne programkrav).

    Rene WAV-filer leses med standardbiblioteket hvis ffmpeg mangler, slik at
    pakken er brukbar i et minimalt miljø.
    """

    def __init__(self, ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe"):
        self.ffmpeg = shutil.which(ffmpeg) or ffmpeg
        self.ffprobe = shutil.which(ffprobe) or ffprobe

    @property
    def har_ffmpeg(self) -> bool:
        return shutil.which(self.ffmpeg) is not None and shutil.which(self.ffprobe) is not None

    # -- filområde ----------------------------------------------------------
    def finn_filer(
        self, rot: Path, rekursivt: bool = True, formater: Iterable[str] = MEDIEFORMATER
    ) -> list[Path]:
        return finn_mediefiler(rot, rekursivt=rekursivt, formater=formater)

    # -- info ---------------------------------------------------------------
    def les_info(self, sti: Path) -> Mediefil:
        sti = Path(sti)
        if not sti.exists():
            raise Mediefeil(f"Finner ikke filen: {sti}")

        if not self.har_ffmpeg:
            return self._info_uten_ffmpeg(sti)

        rå = _kjør(
            [
                self.ffprobe,
                "-v", "error",
                "-show_entries", "format=duration,format_name:stream=codec_type,duration",
                "-of", "json",
                str(sti),
            ]
        )
        data = json.loads(rå or b"{}")
        strømmer = data.get("streams", [])
        typer = {s.get("codec_type") for s in strømmer}

        varighet = 0.0
        for kandidat in [data.get("format", {}).get("duration")] + [s.get("duration") for s in strømmer]:
            try:
                varighet = max(varighet, float(kandidat))
            except (TypeError, ValueError):
                continue

        return Mediefil(
            sti=sti,
            varighet=varighet,
            har_lyd="audio" in typer,
            har_video="video" in typer,
            format=data.get("format", {}).get("format_name", sti.suffix.lstrip(".")),
        )

    def _info_uten_ffmpeg(self, sti: Path) -> Mediefil:
        if sti.suffix.lower() == ".wav":
            with wave.open(str(sti), "rb") as f:
                varighet = f.getnframes() / float(f.getframerate() or 1)
            return Mediefil(sti=sti, varighet=varighet, har_lyd=True, har_video=False, format="wav")
        raise Mediefeil(
            f"Trenger ffmpeg/ffprobe for å lese {sti.name}. Installer ffmpeg, eller bruk WAV-filer."
        )

    # -- lyd ----------------------------------------------------------------
    def les_lyd(
        self, fil: Mediefil, samplerate: int = STANDARD_SAMPLERATE, bit_sekunder: float = 300.0
    ) -> Iterator[Lydstrøm]:
        if not fil.har_lyd:
            return
        if not self.har_ffmpeg:
            yield from self._les_wav(fil, samplerate, bit_sekunder)
            return

        varighet = fil.varighet or 0.0
        start = 0.0
        while True:
            kommando = [self.ffmpeg, "-v", "error", "-nostdin"]
            if start:
                kommando += ["-ss", tidskode(start)]
            kommando += ["-i", str(fil.sti)]
            if bit_sekunder > 0:
                kommando += ["-t", f"{bit_sekunder:.3f}"]
            kommando += ["-vn", "-ac", "1", "-ar", str(samplerate), "-f", "f32le", "-"]

            rå = _kjør(kommando, binærutdata=True)
            if not rå:
                return

            prøver = array("f")
            prøver.frombytes(rå[: len(rå) - (len(rå) % 4)])
            yield Lydstrøm(prøver=prøver, samplerate=samplerate, start=start)

            lest = len(prøver) / samplerate
            start += lest
            if bit_sekunder <= 0 or lest < bit_sekunder * 0.99:
                return
            if varighet and start >= varighet:
                return

    def _les_wav(self, fil: Mediefil, samplerate: int, bit_sekunder: float) -> Iterator[Lydstrøm]:
        """Nødløsning uten ffmpeg: PCM-WAV via standardbiblioteket."""
        if fil.sti.suffix.lower() != ".wav":
            raise Mediefeil(f"Trenger ffmpeg for å dekode lyd fra {fil.sti.name}.")

        with wave.open(str(fil.sti), "rb") as f:
            kanaler = f.getnchannels()
            bredde = f.getsampwidth()
            kilderate = f.getframerate()
            if bredde not in (1, 2, 4):
                raise Mediefeil(f"Støtter ikke {bredde * 8}-bits WAV uten ffmpeg: {fil.sti.name}")

            steg = max(1, int(round(kilderate / samplerate)))
            faktisk_rate = kilderate / steg
            per_bit = int(kilderate * bit_sekunder) if bit_sekunder > 0 else f.getnframes()
            lest_totalt = 0

            while True:
                rammer = f.readframes(max(1, per_bit))
                if not rammer:
                    return
                prøver = _pcm_til_mono(rammer, bredde, kanaler)[::steg]
                start = lest_totalt / kilderate
                lest_totalt += len(rammer) // (bredde * kanaler)
                yield Lydstrøm(prøver=prøver, samplerate=int(round(faktisk_rate)), start=start)

    # -- bilde --------------------------------------------------------------
    def les_rammer(self, fil: Mediefil, per_sekund: float = 1.0) -> Iterator[Bilderamme]:
        if not fil.har_video:
            return
        if not self.har_ffmpeg:
            raise Mediefeil("Trenger ffmpeg for å hente ut videobilder.")

        blokk = 300.0
        varighet = fil.varighet or blokk
        start = 0.0
        while start < varighet:
            with tempfile.TemporaryDirectory(prefix="mediaskann-") as katalog:
                mal = str(Path(katalog) / "ramme_%06d.jpg")
                _kjør(
                    [
                        self.ffmpeg, "-v", "error", "-nostdin",
                        "-ss", tidskode(start),
                        "-i", str(fil.sti),
                        "-t", f"{blokk:.3f}",
                        "-vf", f"fps={per_sekund}",
                        "-q:v", "4",
                        mal,
                    ]
                )
                bilder = sorted(Path(katalog).glob("ramme_*.jpg"))
                if not bilder:
                    return
                for nummer, bilde in enumerate(bilder):
                    yield Bilderamme(tid=start + nummer / per_sekund, data=bilde.read_bytes())
            start += blokk

    # -- uttrekk ------------------------------------------------------------
    def klipp_ut(
        self, fil: Mediefil, start: float, slutt: float, mål: Path, nøyaktig: bool = False
    ) -> Path:
        if not self.har_ffmpeg:
            raise Mediefeil("Trenger ffmpeg for å klippe ut sekvenser.")
        mål = Path(mål)
        mål.parent.mkdir(parents=True, exist_ok=True)

        varighet = max(0.0, slutt - start)
        kommando = [self.ffmpeg, "-v", "error", "-nostdin", "-y"]
        if nøyaktig:
            # Presis (men langsommere) klipping: dekod om.
            kommando += ["-ss", tidskode(start), "-i", str(fil.sti), "-t", f"{varighet:.3f}"]
        else:
            # Rask klipping uten omkoding – starten legges på nærmeste nøkkelbilde.
            kommando += ["-ss", tidskode(start), "-i", str(fil.sti), "-t", f"{varighet:.3f}", "-c", "copy"]
        kommando += [str(mål)]
        _kjør(kommando)
        return mål


def _pcm_til_mono(rammer: bytes, bredde: int, kanaler: int) -> array:
    """Bland PCM-rammer ned til mono i [-1, 1]."""
    if bredde == 1:  # 8-bit WAV er uten fortegn
        verdier = [(b - 128) / 128.0 for b in rammer]
    elif bredde == 2:
        antall = len(rammer) // 2
        verdier = [v / 32768.0 for v in struct.unpack(f"<{antall}h", rammer[: antall * 2])]
    else:
        antall = len(rammer) // 4
        verdier = [v / 2147483648.0 for v in struct.unpack(f"<{antall}i", rammer[: antall * 4])]

    if kanaler > 1:
        verdier = [
            sum(verdier[i : i + kanaler]) / kanaler for i in range(0, len(verdier) - kanaler + 1, kanaler)
        ]
    return array("f", verdier)


class MockMedieleser:
    """Medieleser i minnet – for tester og ``--demo``, uten ffmpeg og disk."""

    def __init__(
        self,
        filer: dict[Path, Mediefil] | None = None,
        lyd: dict[Path, Lydstrøm] | None = None,
        rammer: dict[Path, list[Bilderamme]] | None = None,
    ):
        self.filer = dict(filer or {})
        self.lyd = dict(lyd or {})
        self.rammer = dict(rammer or {})
        self.utklipp: list[tuple[Path, float, float, Path]] = []

    def legg_til(
        self,
        mediefil: Mediefil,
        lyd: Lydstrøm | None = None,
        rammer: list[Bilderamme] | None = None,
    ) -> None:
        self.filer[mediefil.sti] = mediefil
        if lyd is not None:
            self.lyd[mediefil.sti] = lyd
        if rammer is not None:
            self.rammer[mediefil.sti] = rammer

    def finn_filer(
        self, rot: Path, rekursivt: bool = True, formater: Iterable[str] = MEDIEFORMATER
    ) -> list[Path]:
        rot = Path(rot)
        return sorted(
            sti
            for sti in self.filer
            if sti == rot or (rot in sti.parents and (rekursivt or sti.parent == rot))
        )

    def les_info(self, sti: Path) -> Mediefil:
        try:
            return self.filer[Path(sti)]
        except KeyError:
            raise Mediefeil(f"Ukjent fil i mock-leseren: {sti}") from None

    def les_lyd(
        self, fil: Mediefil, samplerate: int = STANDARD_SAMPLERATE, bit_sekunder: float = 300.0
    ) -> Iterator[Lydstrøm]:
        strøm = self.lyd.get(fil.sti)
        if strøm is not None:
            yield strøm

    def les_rammer(self, fil: Mediefil, per_sekund: float = 1.0) -> Iterator[Bilderamme]:
        yield from self.rammer.get(fil.sti, [])

    def klipp_ut(
        self, fil: Mediefil, start: float, slutt: float, mål: Path, nøyaktig: bool = False
    ) -> Path:
        self.utklipp.append((fil.sti, start, slutt, Path(mål)))
        return Path(mål)
