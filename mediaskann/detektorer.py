"""Detektorene – bak protokoller, slik at modellene er utbyttbare.

Kjernen (skanning, segmentering, rapport, uttrekk) kjenner bare
``Lyddetektor`` og ``Bildedetektor``. Implementasjonene her bruker tunge
valgfrie pakker (TensorFlow Hub / Ultralytics / OpenCV) og importeres først
når detektoren faktisk opprettes – akkurat som ``AnthropicKlient`` i
``coach``-pakken.

Alle detektorer returnerer ``Funn`` med **absolutt tid i mediefilen**.
"""

from __future__ import annotations

import io
from typing import Callable, Iterable, Iterator, Protocol, runtime_checkable

from .klasser import bildetype, lydtype
from .models import Bilderamme, Funn, Hendelsestype, Kilde, Lydstrøm, Mediefil

YAMNET_URL = "https://tfhub.dev/google/yamnet/1"
STANDARD_YOLO = "yolov8n.pt"


class Detektorfeil(Exception):
    """Detektoren kunne ikke lastes eller kjøres."""


@runtime_checkable
class Lyddetektor(Protocol):
    """Klassifiserer lyd. ``samplerate`` er raten detektoren vil ha lyden i."""

    samplerate: int

    def analyser_lyd(self, fil: Mediefil, lyd: Lydstrøm) -> list[Funn]:
        ...


@runtime_checkable
class Bildedetektor(Protocol):
    """Finner objekter i videobilder. Tar imot flere rammer for å kunne batche."""

    def analyser_rammer(self, fil: Mediefil, rammer: Iterable[Bilderamme]) -> list[Funn]:
        ...


# --------------------------------------------------------------------------
# Lyd: YAMNet (AudioSet, 521 klasser – dekker både menneskelyd og dyrelyd)
# --------------------------------------------------------------------------
class YamnetLyddetektor:
    """Klassifiserer lyd med YAMNet: tale, latter, gråt, sang, bjeffing, fuglesang …

    Krever ``tensorflow`` og ``tensorflow_hub``. Modellen lastes ned første
    gang (eller leses fra ``TFHUB_CACHE_DIR``).
    """

    samplerate = 16000
    _vindu = 0.96
    _steg = 0.48

    def __init__(self, modelladresse: str = YAMNET_URL, minste_score: float = 0.05):
        self.modelladresse = modelladresse
        self.minste_score = minste_score
        self._modell = None
        self._klassenavn: list[str] = []
        self._indekser: dict[Hendelsestype, list[int]] = {}

    def _last(self) -> None:
        if self._modell is not None:
            return
        try:
            import csv

            import tensorflow_hub as hub  # type: ignore
        except ImportError as exc:  # pragma: no cover - avhenger av miljøet
            raise Detektorfeil(
                "YamnetLyddetektor trenger tensorflow og tensorflow_hub "
                "(pip install tensorflow tensorflow_hub)."
            ) from exc

        self._modell = hub.load(self.modelladresse)
        sti = self._modell.class_map_path().numpy().decode("utf-8")
        with open(sti, newline="", encoding="utf-8") as f:
            self._klassenavn = [rad["display_name"] for rad in csv.DictReader(f)]

        self._indekser = {Hendelsestype.MENNESKESTEMME: [], Hendelsestype.DYRELYD: []}
        for indeks, navn in enumerate(self._klassenavn):
            type_ = lydtype(navn)
            if type_ is not None:
                self._indekser[type_].append(indeks)

    def analyser_lyd(self, fil: Mediefil, lyd: Lydstrøm) -> list[Funn]:
        self._last()
        import numpy as np  # type: ignore

        if lyd.samplerate != self.samplerate:
            raise Detektorfeil(
                f"YAMNet vil ha {self.samplerate} Hz, fikk {lyd.samplerate} Hz."
            )
        bølge = np.frombuffer(lyd.prøver.tobytes(), dtype=np.float32)
        if bølge.size < int(self.samplerate * self._vindu):
            return []

        scorer = self._modell(bølge)[0].numpy()  # [rammer, 521]

        funn: list[Funn] = []
        for ramme, rad in enumerate(scorer):
            start = lyd.start + ramme * self._steg
            for type_, indekser in self._indekser.items():
                if not indekser:
                    continue
                beste = max(indekser, key=lambda i: rad[i])
                score = float(rad[beste])
                if score < self.minste_score:
                    continue
                funn.append(
                    Funn(
                        type=type_,
                        start=start,
                        slutt=start + self._vindu,
                        score=score,
                        kilde=Kilde.LYD,
                        etikett=self._klassenavn[beste],
                    )
                )
        return funn


# --------------------------------------------------------------------------
# Bilde: YOLO (COCO – «person» og de ti dyreklassene)
# --------------------------------------------------------------------------
class YoloBildedetektor:
    """Finner mennesker og dyr i videobilder med en YOLO-modell (Ultralytics).

    Krever ``ultralytics`` og ``pillow``. Vektene lastes ned første gang.
    """

    def __init__(
        self,
        modell: str = STANDARD_YOLO,
        minste_score: float = 0.25,
        batchstørrelse: int = 16,
    ):
        self.modellnavn = modell
        self.minste_score = minste_score
        self.batchstørrelse = max(1, batchstørrelse)
        self._modell = None

    def _last(self):
        if self._modell is None:
            try:
                from ultralytics import YOLO  # type: ignore
            except ImportError as exc:  # pragma: no cover - avhenger av miljøet
                raise Detektorfeil(
                    "YoloBildedetektor trenger ultralytics (pip install ultralytics pillow)."
                ) from exc
            self._modell = YOLO(self.modellnavn)
        return self._modell

    @staticmethod
    def _til_bilde(ramme: Bilderamme):
        try:
            from PIL import Image  # type: ignore
        except ImportError as exc:  # pragma: no cover - avhenger av miljøet
            raise Detektorfeil("YoloBildedetektor trenger pillow (pip install pillow).") from exc
        return Image.open(io.BytesIO(ramme.data)).convert("RGB")

    def analyser_rammer(self, fil: Mediefil, rammer: Iterable[Bilderamme]) -> list[Funn]:
        modell = self._last()
        funn: list[Funn] = []

        for gruppe in _grupper(rammer, self.batchstørrelse):
            bilder = [self._til_bilde(r) for r in gruppe]
            resultater = modell.predict(bilder, verbose=False, conf=self.minste_score)
            for ramme, resultat in zip(gruppe, resultater):
                navn = resultat.names
                for boks in resultat.boxes:
                    klasse = navn[int(boks.cls)]
                    type_ = bildetype(klasse)
                    if type_ is None:
                        continue
                    score = float(boks.conf)
                    if score < self.minste_score:
                        continue
                    funn.append(
                        Funn(
                            type=type_,
                            start=ramme.tid,
                            slutt=ramme.tid,
                            score=score,
                            kilde=Kilde.BILDE,
                            etikett=klasse,
                        )
                    )
        return funn


class OpenCVPersondetektor:
    """Personer i bildet med OpenCVs innebygde HOG-detektor.

    Enklere og svakere enn YOLO, men krever bare ``opencv-python`` og laster
    ikke ned noen modell. Finner kun mennesker – ikke dyr.
    """

    #: HOG gir en SVM-vekt, ikke en sannsynlighet. Vi deler på denne for å få
    #: en score på samme 0–1-skala som de andre detektorene.
    VEKTSKALA = 1.5

    def __init__(self, minste_score: float = 0.4, skala: float = 1.05):
        self.minste_score = minste_score
        self.skala = skala
        self._hog = None

    def _last(self):
        if self._hog is None:
            try:
                import cv2  # type: ignore
            except ImportError as exc:  # pragma: no cover - avhenger av miljøet
                raise Detektorfeil(
                    "OpenCVPersondetektor trenger opencv-python (pip install opencv-python)."
                ) from exc
            hog = cv2.HOGDescriptor()
            hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            self._hog = hog
        return self._hog

    def analyser_rammer(self, fil: Mediefil, rammer: Iterable[Bilderamme]) -> list[Funn]:
        hog = self._last()
        import cv2  # type: ignore
        import numpy as np  # type: ignore

        funn: list[Funn] = []
        for ramme in rammer:
            bilde = cv2.imdecode(np.frombuffer(ramme.data, dtype=np.uint8), cv2.IMREAD_COLOR)
            if bilde is None:
                continue
            _, vekter = hog.detectMultiScale(bilde, winStride=(8, 8), scale=self.skala)
            for vekt in vekter:
                score = min(1.0, float(vekt) / self.VEKTSKALA)
                if score < self.minste_score:
                    continue
                funn.append(
                    Funn(
                        type=Hendelsestype.MENNESKE_SYNLIG,
                        start=ramme.tid,
                        slutt=ramme.tid,
                        score=score,
                        kilde=Kilde.BILDE,
                        etikett="person",
                    )
                )
        return funn


# --------------------------------------------------------------------------
# Mock-detektorer – tester og demo
# --------------------------------------------------------------------------
class MockLyddetektor:
    """Returnerer ferdigskrevne funn per fil. Ingen modeller involvert."""

    def __init__(
        self,
        funn: dict[str, list[Funn]] | None = None,
        samplerate: int = 16000,
        regel: Callable[[Mediefil, Lydstrøm], list[Funn]] | None = None,
    ):
        self.funn = {str(k): v for k, v in (funn or {}).items()}
        self.samplerate = samplerate
        self.regel = regel

    def analyser_lyd(self, fil: Mediefil, lyd: Lydstrøm) -> list[Funn]:
        if self.regel is not None:
            return list(self.regel(fil, lyd))
        return list(self.funn.get(str(fil.sti), []))


class MockBildedetektor:
    """Returnerer ferdigskrevne funn per fil."""

    def __init__(
        self,
        funn: dict[str, list[Funn]] | None = None,
        regel: Callable[[Mediefil, Bilderamme], list[Funn]] | None = None,
    ):
        self.funn = {str(k): v for k, v in (funn or {}).items()}
        self.regel = regel

    def analyser_rammer(self, fil: Mediefil, rammer: Iterable[Bilderamme]) -> list[Funn]:
        if self.regel is not None:
            resultat: list[Funn] = []
            for ramme in rammer:
                resultat.extend(self.regel(fil, ramme))
            return resultat
        list(rammer)  # tøm iteratoren, som en ekte detektor ville gjort
        return list(self.funn.get(str(fil.sti), []))


def _grupper(elementer: Iterable[Bilderamme], størrelse: int) -> Iterator[list[Bilderamme]]:
    gruppe: list[Bilderamme] = []
    for element in elementer:
        gruppe.append(element)
        if len(gruppe) >= størrelse:
            yield gruppe
            gruppe = []
    if gruppe:
        yield gruppe
