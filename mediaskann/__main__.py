"""Kommandolinje: skann et filområde og hent ut sekvenser med mennesker og dyr.

Eksempler:
    python -m mediaskann /opptak --json rapport.json
    python -m mediaskann /opptak --typer stemme,dyrelyd --klipp utklipp/
    python -m mediaskann --demo          # hele løpet med simulerte detektorer
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from array import array
from pathlib import Path

from .detektorer import (
    MockBildedetektor,
    MockLyddetektor,
    OpenCVPersondetektor,
    YamnetLyddetektor,
    YoloBildedetektor,
)
from .media import FFmpegLeser, Mediefeil, MockMedieleser, finn_mediefiler
from .models import (
    Bilderamme,
    Funn,
    Hendelsestype,
    Kilde,
    Lydstrøm,
    Mediefil,
)
from .rapport import skriv_csv, skriv_json, tekstrapport
from .segmentering import STANDARDTERSKLER, Segmenteringsvalg
from .skanner import ALLE_TYPER, Skanner, Skannvalg
from .uttrekk import klipp_ut_sekvenser

TYPEALIAS = {
    "alle": set(ALLE_TYPER),
    "menneske": {Hendelsestype.MENNESKE_SYNLIG},
    "mennesker": {Hendelsestype.MENNESKE_SYNLIG},
    "menneske_synlig": {Hendelsestype.MENNESKE_SYNLIG},
    "stemme": {Hendelsestype.MENNESKESTEMME},
    "tale": {Hendelsestype.MENNESKESTEMME},
    "menneskelyd": {Hendelsestype.MENNESKESTEMME},
    "menneskestemme": {Hendelsestype.MENNESKESTEMME},
    "dyr": {Hendelsestype.DYR_SYNLIG},
    "dyr_synlig": {Hendelsestype.DYR_SYNLIG},
    "dyrelyd": {Hendelsestype.DYRELYD},
    "lyd": {Hendelsestype.MENNESKESTEMME, Hendelsestype.DYRELYD},
    "bilde": {Hendelsestype.MENNESKE_SYNLIG, Hendelsestype.DYR_SYNLIG},
}


def _tolk_typer(tekst: str) -> frozenset[Hendelsestype]:
    valgte: set[Hendelsestype] = set()
    for del_ in tekst.split(","):
        nøkkel = del_.strip().lower()
        if not nøkkel:
            continue
        if nøkkel not in TYPEALIAS:
            gyldige = ", ".join(sorted(TYPEALIAS))
            raise argparse.ArgumentTypeError(f"Ukjent type «{del_}». Gyldige: {gyldige}")
        valgte |= TYPEALIAS[nøkkel]
    if not valgte:
        raise argparse.ArgumentTypeError("Oppgi minst én type.")
    return frozenset(valgte)


def _lag_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mediaskann",
        description="Skann et filområde for sekvenser med mennesker, menneskelyd og dyr.",
    )
    parser.add_argument("område", nargs="?", help="katalog (eller enkeltfil) som skal skannes")
    parser.add_argument("--demo", action="store_true", help="kjør mot simulerte data, uten ffmpeg/modeller")
    parser.add_argument("--liste", action="store_true", help="bare list mediefilene som ville blitt skannet")

    parser.add_argument(
        "--typer",
        type=_tolk_typer,
        default=ALLE_TYPER,
        help="hva det skal letes etter: menneske, stemme, dyr, dyrelyd, lyd, bilde, alle (komma-separert)",
    )
    parser.add_argument("--ikke-rekursivt", action="store_true", help="ikke gå ned i undermapper")
    parser.add_argument("--fps", type=float, default=1.0, help="videobilder analysert per sekund (standard 1)")

    parser.add_argument("--terskel", type=float, help="samme terskel for alle typer (0–1)")
    parser.add_argument("--terskel-lyd", type=float, help="terskel for lydtypene")
    parser.add_argument("--terskel-bilde", type=float, help="terskel for bildetypene")
    parser.add_argument("--min-varighet", type=float, default=0.8, help="korteste sekvens vi beholder")
    parser.add_argument("--maks-hull", type=float, default=1.5, help="opphold som tåles inne i en sekvens")
    parser.add_argument("--padding", type=float, default=0.5, help="luft lagt på i hver ende")

    parser.add_argument("--lydmodell", choices=["yamnet", "ingen"], default="yamnet")
    parser.add_argument("--bildemodell", choices=["yolo", "hog", "ingen"], default="yolo")
    parser.add_argument("--yolo-vekter", default="yolov8n.pt", help="vektfil/modellnavn for YOLO")

    parser.add_argument("--json", dest="json_sti", help="skriv full rapport som JSON")
    parser.add_argument("--csv", dest="csv_sti", help="skriv sekvensene som CSV")
    parser.add_argument("--klipp", help="klipp sekvensene ut til denne katalogen")
    parser.add_argument("--flat", action="store_true", help="legg utklippene rett i katalogen, uten mappe per type")
    parser.add_argument(
        "--nøyaktig",
        action="store_true",
        help="klipp presist ved å kode om (tregere; standard er raskt kopi-klipp på nøkkelbilde)",
    )
    parser.add_argument("--stille", action="store_true", help="ikke skriv framdrift underveis")
    return parser


def _segmenteringsvalg(args: argparse.Namespace) -> Segmenteringsvalg:
    terskler = dict(STANDARDTERSKLER)
    if args.terskel is not None:
        terskler = {type_: args.terskel for type_ in Hendelsestype}
    if args.terskel_lyd is not None:
        for type_ in Hendelsestype:
            if type_.er_lyd:
                terskler[type_] = args.terskel_lyd
    if args.terskel_bilde is not None:
        for type_ in Hendelsestype:
            if not type_.er_lyd:
                terskler[type_] = args.terskel_bilde
    return Segmenteringsvalg(
        terskler=terskler,
        maks_hull=args.maks_hull,
        min_varighet=args.min_varighet,
        padding=args.padding,
    )


def _mangler(pakke: str) -> bool:
    return importlib.util.find_spec(pakke) is None


def _lag_detektorer(args: argparse.Namespace, skriv) -> tuple[object | None, object | None]:
    lyddetektor = None
    bildedetektor = None
    trenger_lyd = any(t.er_lyd for t in args.typer)
    trenger_bilde = any(not t.er_lyd for t in args.typer)

    if trenger_lyd and args.lydmodell == "yamnet":
        if _mangler("tensorflow_hub"):
            skriv(
                "Advarsel: tensorflow_hub mangler – hopper over lydanalysen.\n"
                "          pip install tensorflow tensorflow_hub"
            )
        else:
            lyddetektor = YamnetLyddetektor()

    if trenger_bilde and args.bildemodell != "ingen":
        if args.bildemodell == "yolo":
            if _mangler("ultralytics"):
                skriv(
                    "Advarsel: ultralytics mangler – hopper over bildeanalysen.\n"
                    "          pip install ultralytics pillow  (eller bruk --bildemodell hog)"
                )
            else:
                bildedetektor = YoloBildedetektor(modell=args.yolo_vekter)
        else:
            if _mangler("cv2"):
                skriv("Advarsel: opencv-python mangler – hopper over bildeanalysen.")
            else:
                bildedetektor = OpenCVPersondetektor()

    return lyddetektor, bildedetektor


def _demo_oppsett() -> tuple[MockMedieleser, MockLyddetektor, MockBildedetektor, Path]:
    """Litt eksempeldata, slik at hele løpet kan vises uten ffmpeg og modeller."""
    rot = Path("/demo/opptak")
    video = Mediefil(sti=rot / "intervju.avi", varighet=60.0, har_lyd=True, har_video=True, format="avi")
    lydfil = Mediefil(sti=rot / "uteopptak.wav", varighet=30.0, har_lyd=True, har_video=False, format="wav")

    leser = MockMedieleser()
    leser.legg_til(
        video,
        lyd=Lydstrøm(prøver=array("f", [0.0] * 16000), samplerate=16000),
        rammer=[Bilderamme(tid=float(t), data=b"") for t in range(0, 60)],
    )
    leser.legg_til(lydfil, lyd=Lydstrøm(prøver=array("f", [0.0] * 16000), samplerate=16000))

    def lydfunn(start: float, slutt: float, type_: Hendelsestype, etikett: str, score: float = 0.8):
        # Ett funn per halve sekund, slik en ekte lydklassifikator gir dem.
        return [
            Funn(type=type_, start=t / 2, slutt=t / 2 + 0.96, score=score, kilde=Kilde.LYD, etikett=etikett)
            for t in range(int(start * 2), int(slutt * 2))
        ]

    lyddetektor = MockLyddetektor(
        {
            str(video.sti): (
                lydfunn(2, 14, Hendelsestype.MENNESKESTEMME, "Speech")
                + lydfunn(20, 26, Hendelsestype.MENNESKESTEMME, "Laughter", 0.6)
                + lydfunn(41, 47, Hendelsestype.DYRELYD, "Bark", 0.7)
            ),
            str(lydfil.sti): (
                lydfunn(1, 9, Hendelsestype.DYRELYD, "Bird vocalization, bird call, bird song", 0.75)
                + lydfunn(18, 23, Hendelsestype.MENNESKESTEMME, "Conversation", 0.55)
            ),
        }
    )

    def bildefunn(fra: int, til: int, type_: Hendelsestype, etikett: str, score: float = 0.9):
        return [
            Funn(type=type_, start=float(t), slutt=float(t), score=score, kilde=Kilde.BILDE, etikett=etikett)
            for t in range(fra, til)
        ]

    bildedetektor = MockBildedetektor(
        {
            str(video.sti): (
                bildefunn(1, 15, Hendelsestype.MENNESKE_SYNLIG, "person")
                + bildefunn(19, 27, Hendelsestype.MENNESKE_SYNLIG, "person", 0.82)
                + bildefunn(40, 48, Hendelsestype.DYR_SYNLIG, "dog", 0.66)
            )
        }
    )
    return leser, lyddetektor, bildedetektor, rot


def main(argv: list[str] | None = None) -> int:
    parser = _lag_parser()
    args = parser.parse_args(argv)

    def skriv(melding: str) -> None:
        if not args.stille:
            print(melding, file=sys.stderr)

    if not args.demo and not args.område:
        parser.error("oppgi et filområde, eller bruk --demo")

    valg = Skannvalg(
        typer=args.typer,
        rammer_per_sekund=args.fps,
        rekursivt=not args.ikke_rekursivt,
        segmentering=_segmenteringsvalg(args),
    )

    if args.demo:
        leser, lyddetektor, bildedetektor, rot = _demo_oppsett()
    else:
        rot = Path(args.område)
        leser = FFmpegLeser()
        if not leser.har_ffmpeg:
            skriv(
                "Advarsel: finner ikke ffmpeg/ffprobe. Bare PCM-WAV kan leses.\n"
                "          Installer ffmpeg for video og andre lydformater."
            )
        if args.liste:
            try:
                for sti in finn_mediefiler(rot, rekursivt=valg.rekursivt, formater=valg.formater):
                    print(sti)
            except Mediefeil as exc:
                print(f"Feil: {exc}", file=sys.stderr)
                return 1
            return 0
        lyddetektor, bildedetektor = _lag_detektorer(args, skriv)
        if lyddetektor is None and bildedetektor is None:
            print(
                "Ingen detektorer tilgjengelig – da er det ingenting å analysere.\n"
                "Installer minst én: tensorflow+tensorflow_hub (lyd) eller ultralytics (bilde).",
                file=sys.stderr,
            )
            return 2

    skanner = Skanner(
        leser=leser,
        lyddetektor=lyddetektor,
        bildedetektor=bildedetektor,
        valg=valg,
        logg=skriv,
    )

    try:
        resultat = skanner.skann_område(rot)
    except Mediefeil as exc:
        print(f"Feil: {exc}", file=sys.stderr)
        return 1

    print(tekstrapport(resultat))

    if args.json_sti:
        skriv(f"Skrev rapport til {skriv_json(resultat, args.json_sti)}")
    if args.csv_sti:
        skriv(f"Skrev CSV til {skriv_csv(resultat.sekvenser, args.csv_sti)}")
    if args.klipp:
        utklipp = klipp_ut_sekvenser(
            leser=leser,
            sekvenser=resultat.sekvenser,
            målkatalog=args.klipp,
            per_type=not args.flat,
            nøyaktig=args.nøyaktig,
            logg=skriv,
        )
        skriv(f"Klippet ut {len(utklipp)} sekvens(er) til {args.klipp}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
