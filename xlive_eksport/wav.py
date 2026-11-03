"""Lesing og skriving av WAV-filer uten eksterne avhengigheter.

* ``les_wav_info`` leser headeren til en X-Live-take (``00000001.WAV`` …)
  og finner hvor lyddataene ligger. Tåler filer der headeren ikke ble
  oppdatert (f.eks. strømbrudd under opptak): da brukes filstørrelsen.
* ``WavSkriver`` skriver PCM-WAV med valgfrie markører (``cue``/``labl``,
  leses av bl.a. REAPER, Cubase og Nuendo). Blir filen større enn 4 GB,
  gjøres den automatisk om til RF64 (EBU Tech 3306).
* ``del_ut_kanaler`` henter ut én eller flere kanaler fra en interleavet
  buffer og konverterer bitdybde. Alt gjøres med utvidet slicing på
  ``bytes``, som kjører i C – derfor er det raskt nok i ren Python.
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass
from typing import BinaryIO, Sequence

WAVE_FORMAT_PCM = 0x0001
WAVE_FORMAT_IEEE_FLOAT = 0x0003
WAVE_FORMAT_EXTENSIBLE = 0xFFFE


class WavFeil(Exception):
    """Filen er ikke en WAV-fil vi forstår."""


@dataclass
class WavInfo:
    sti: str
    kanaler: int
    samplerate: int
    bits: int
    formattag: int          # 1 = PCM-heltall, 3 = flyttall
    data_start: int         # byte-offset der lyddata begynner
    data_lengde: int        # antall byte lyddata (justert til hele frames)

    @property
    def bytes_per_sample(self) -> int:
        return self.bits // 8

    @property
    def frame_storrelse(self) -> int:
        return self.kanaler * self.bytes_per_sample

    @property
    def frames(self) -> int:
        return self.data_lengde // self.frame_storrelse


def les_wav_info(sti: str) -> WavInfo:
    filstorrelse = os.path.getsize(sti)
    with open(sti, "rb") as f:
        hode = f.read(12)
        if len(hode) < 12 or hode[8:12] != b"WAVE" or hode[:4] not in (b"RIFF", b"RF64"):
            raise WavFeil(f"{sti}: ikke en WAV-fil")
        er_rf64 = hode[:4] == b"RF64"
        ds64_data = None
        fmt = None
        pos = 12
        while pos + 8 <= filstorrelse:
            f.seek(pos)
            ch = f.read(8)
            if len(ch) < 8:
                break
            cid, storrelse = ch[:4], struct.unpack("<I", ch[4:])[0]
            if cid == b"ds64":
                d = f.read(min(storrelse, 28))
                if len(d) >= 16:
                    ds64_data = struct.unpack("<Q", d[8:16])[0]
            elif cid == b"fmt ":
                fmt = f.read(min(storrelse, 40))
            elif cid == b"data":
                if fmt is None or len(fmt) < 16:
                    raise WavFeil(f"{sti}: mangler fmt-chunk før data")
                tag, kan, sr, _bps, _align, bits = struct.unpack("<HHIIHH", fmt[:16])
                if tag == WAVE_FORMAT_EXTENSIBLE and len(fmt) >= 26:
                    tag = struct.unpack("<H", fmt[24:26])[0]
                if tag not in (WAVE_FORMAT_PCM, WAVE_FORMAT_IEEE_FLOAT):
                    raise WavFeil(f"{sti}: ukjent lydformat {tag:#x}")
                start = pos + 8
                tilgjengelig = filstorrelse - start
                if er_rf64 and storrelse == 0xFFFFFFFF and ds64_data is not None:
                    storrelse = ds64_data
                # 0 eller for stor = header ble ikke ferdigskrevet. Bruk filen.
                if storrelse == 0 or storrelse > tilgjengelig:
                    storrelse = tilgjengelig
                frame = kan * (bits // 8)
                storrelse -= storrelse % frame
                return WavInfo(sti, kan, sr, bits, tag, start, storrelse)
            pos += 8 + storrelse + (storrelse & 1)
    raise WavFeil(f"{sti}: fant ingen data-chunk")


# --------------------------------------------------------------------------
# Kanaluttrekk
# --------------------------------------------------------------------------

def del_ut_kanaler(
    buffer: bytes,
    kanaler_totalt: int,
    kilde_bps: int,
    valgte: Sequence[int],
    mal_bps: int,
) -> bytes:
    """Hent ``valgte`` kanaler (0-basert) fra en interleavet PCM-buffer.

    Bitdybde konverteres ved å beholde de mest signifikante bytene
    (little endian), f.eks. 32 → 24 bit ved å droppe laveste byte.
    Resultatet er interleavet i rekkefølgen i ``valgte``.
    """
    if mal_bps > kilde_bps:
        raise ValueError("kan ikke øke bitdybden")
    steg = kanaler_totalt * kilde_bps
    hopp = kilde_bps - mal_bps          # antall lave byte som droppes
    ut_kan = len(valgte)
    frames = len(buffer) // steg
    ut = bytearray(frames * ut_kan * mal_bps)
    ut_steg = ut_kan * mal_bps
    for i, kanal in enumerate(valgte):
        for b in range(mal_bps):
            kilde_off = kanal * kilde_bps + hopp + b
            ut[i * mal_bps + b::ut_steg] = buffer[kilde_off:frames * steg:steg]
    return bytes(ut)


def er_digital_stillhet(data: bytes) -> bool:
    return not data.strip(b"\x00")


# --------------------------------------------------------------------------
# Skriving
# --------------------------------------------------------------------------

@dataclass
class Markor:
    sample: int
    navn: str


class WavSkriver:
    """Skriv PCM-WAV. Header fylles inn ved ``lukk``.

    Vi reserverer en 28-byte ``JUNK``-chunk rett etter ``RIFF``-headeren,
    som blir til ``ds64`` dersom filen passerer 4 GB (RF64).
    """

    MAKS_RIFF = 0xFFFFFFFF

    def __init__(self, sti: str, kanaler: int, samplerate: int, bits: int,
                 formattag: int = WAVE_FORMAT_PCM):
        self.sti = sti
        self.kanaler = kanaler
        self.samplerate = samplerate
        self.bits = bits
        self.formattag = formattag
        self.data_byte = 0
        self.markorer: list[Markor] = []
        self._f: BinaryIO = open(sti, "wb")
        self._skriv_header(endelig=False)

    def _fmt_chunk(self) -> bytes:
        align = self.kanaler * self.bits // 8
        return b"fmt " + struct.pack(
            "<IHHIIHH", 16, self.formattag, self.kanaler, self.samplerate,
            self.samplerate * align, align, self.bits)

    def _skriv_header(self, endelig: bool) -> None:
        etter_data = self._etter_data() if endelig else b""
        # "WAVE" + JUNK/ds64 (8+28) + fmt (8+16) + data-header (8) + data
        riff_storrelse = (4 + 36 + 24 + 8 + self.data_byte + (self.data_byte & 1)
                          + len(etter_data))
        rf64 = endelig and riff_storrelse > self.MAKS_RIFF
        self._f.seek(0)
        if rf64:
            frames = self.data_byte // (self.kanaler * self.bits // 8)
            self._f.write(b"RF64" + struct.pack("<I", 0xFFFFFFFF) + b"WAVE")
            self._f.write(b"ds64" + struct.pack("<IQQQI", 28, riff_storrelse, self.data_byte, frames, 0))
        else:
            self._f.write(b"RIFF" + struct.pack("<I", riff_storrelse) + b"WAVE")
            self._f.write(b"JUNK" + struct.pack("<I", 28) + bytes(28))
        self._f.write(self._fmt_chunk())
        data_felt = 0xFFFFFFFF if rf64 else self.data_byte
        self._f.write(b"data" + struct.pack("<I", data_felt))

    def skriv(self, data: bytes) -> None:
        self._f.write(data)
        self.data_byte += len(data)

    def _etter_data(self) -> bytes:
        if not self.markorer:
            return b""
        punkter = b"".join(
            struct.pack("<II4sIII", i + 1, m.sample, b"data", 0, 0, m.sample)
            for i, m in enumerate(self.markorer))
        cue = b"cue " + struct.pack("<II", 4 + len(punkter), len(self.markorer)) + punkter
        labl = b""
        for i, m in enumerate(self.markorer):
            tekst = m.navn.encode("utf-8", "replace") + b"\x00"
            innhold = struct.pack("<I", i + 1) + tekst
            labl += b"labl" + struct.pack("<I", len(innhold)) + innhold
            if len(innhold) & 1:
                labl += b"\x00"
        liste = b"LIST" + struct.pack("<I", 4 + len(labl)) + b"adtl" + labl
        return cue + liste

    def lukk(self) -> None:
        if self.data_byte & 1:
            self._f.write(b"\x00")
        self._f.write(self._etter_data())
        self._skriv_header(endelig=True)
        self._f.close()

    def __enter__(self) -> "WavSkriver":
        return self

    def __exit__(self, *exc) -> None:
        self.lukk()
