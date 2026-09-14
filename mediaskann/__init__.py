"""mediaskann – finn sekvenser med mennesker, menneskelyd og dyr i et filområde.

Pakken går gjennom en katalog med video- og lydfiler (avi, mp4, mkv, mov,
mp3, wav, flac, m4a …), analyserer lyd og bilde, og gir deg tidskodede
sekvenser du kan lese som rapport (JSON/CSV) eller klippe rett ut til egne
filer.

Fire hendelsestyper: mennesker i bildet, lyd av mennesker (tale, latter,
gråt, sang, rop), dyr i bildet og lyd av dyr (bjeffing, fuglesang, mjauing …).

Som ``dmx_spot_detect`` og ``coach`` er kjernen ren Python
(standardbibliotek) og testbar uten maskinvare: filsøk, segmentering,
rapport og uttrekk jobber mot protokollene ``Medieleser``, ``Lyddetektor``
og ``Bildedetektor``. De tunge delene – ffmpeg for lesing/klipping, YAMNet
for lyd og YOLO for bilde – ligger bak de protokollene og importeres først
når de faktisk brukes.

    from mediaskann import Skanner, FFmpegLeser, YamnetLyddetektor, YoloBildedetektor

    skanner = Skanner(FFmpegLeser(), YamnetLyddetektor(), YoloBildedetektor())
    resultat = skanner.skann_område("/opptak")
    for sekvens in resultat.sekvenser:
        print(sekvens.fil, sekvens.start, sekvens.slutt, sekvens.type.etikett)
"""

from .detektorer import (
    Bildedetektor,
    Detektorfeil,
    Lyddetektor,
    MockBildedetektor,
    MockLyddetektor,
    OpenCVPersondetektor,
    YamnetLyddetektor,
    YoloBildedetektor,
)
from .klasser import (
    DYRELYD_KLASSER,
    DYR_BILDEKLASSER,
    MENNESKELYD_KLASSER,
    MENNESKE_BILDEKLASSER,
    bildetype,
    lydtype,
)
from .media import (
    FFmpegLeser,
    Mediefeil,
    Medieleser,
    MockMedieleser,
    finn_mediefiler,
)
from .models import (
    Bilderamme,
    Filresultat,
    Funn,
    Hendelsestype,
    Kilde,
    LYDFORMATER,
    Lydstrøm,
    MEDIEFORMATER,
    Mediefil,
    Sekvens,
    Skannresultat,
    VIDEOFORMATER,
    tidskode,
)
from .rapport import skriv_csv, skriv_json, som_json, tekstrapport
from .segmentering import (
    STANDARDTERSKLER,
    Segmenteringsvalg,
    lag_sekvenser,
    slå_sammen_typer,
    utvid_punktfunn,
)
from .skanner import ALLE_TYPER, Skanner, Skannvalg
from .uttrekk import Utklipp, filnavn_for, klipp_ut_sekvenser

__all__ = [
    "ALLE_TYPER",
    "Bildedetektor",
    "Bilderamme",
    "DYRELYD_KLASSER",
    "DYR_BILDEKLASSER",
    "Detektorfeil",
    "FFmpegLeser",
    "Filresultat",
    "Funn",
    "Hendelsestype",
    "Kilde",
    "LYDFORMATER",
    "Lyddetektor",
    "Lydstrøm",
    "MEDIEFORMATER",
    "MENNESKELYD_KLASSER",
    "MENNESKE_BILDEKLASSER",
    "Mediefeil",
    "Mediefil",
    "Medieleser",
    "MockBildedetektor",
    "MockLyddetektor",
    "MockMedieleser",
    "OpenCVPersondetektor",
    "STANDARDTERSKLER",
    "Segmenteringsvalg",
    "Sekvens",
    "Skanner",
    "Skannresultat",
    "Skannvalg",
    "Utklipp",
    "VIDEOFORMATER",
    "YamnetLyddetektor",
    "YoloBildedetektor",
    "bildetype",
    "filnavn_for",
    "finn_mediefiler",
    "klipp_ut_sekvenser",
    "lag_sekvenser",
    "lydtype",
    "skriv_csv",
    "skriv_json",
    "slå_sammen_typer",
    "som_json",
    "tekstrapport",
    "tidskode",
    "utvid_punktfunn",
]
