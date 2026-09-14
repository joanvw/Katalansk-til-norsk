"""Fra enkeltfunn til sammenhengende sekvenser – ren, testbar logikk.

Detektorene gir mange små funn (ett per lydramme eller videobilde). Her
slås de sammen til de sekvensene man faktisk vil klippe ut: hold over
terskel, tål korte opphold, dropp glimt som er for korte, og legg på litt
luft i hver ende.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from .models import Funn, Hendelsestype, Kilde, Sekvens

#: Fornuftige startverdier. Lyd og bilde scorer ulikt, derfor egne terskler.
STANDARDTERSKLER: dict[Hendelsestype, float] = {
    Hendelsestype.MENNESKESTEMME: 0.35,
    Hendelsestype.DYRELYD: 0.30,
    Hendelsestype.MENNESKE_SYNLIG: 0.40,
    Hendelsestype.DYR_SYNLIG: 0.40,
}


@dataclass
class Segmenteringsvalg:
    """Hvordan funn skal bli til sekvenser."""

    terskler: dict[Hendelsestype, float] = field(
        default_factory=lambda: dict(STANDARDTERSKLER)
    )
    #: Opphold (sekunder) vi tåler inne i én sekvens før den deles i to.
    maks_hull: float = 1.5
    #: Sekvenser kortere enn dette regnes som støy og forkastes.
    min_varighet: float = 0.8
    #: Luft som legges på i hver ende av en sekvens.
    padding: float = 0.5

    def terskel(self, type_: Hendelsestype) -> float:
        return self.terskler.get(type_, STANDARDTERSKLER.get(type_, 0.35))


def lag_sekvenser(
    fil: Path,
    funn: Iterable[Funn],
    valg: Segmenteringsvalg | None = None,
    filvarighet: float = 0.0,
) -> list[Sekvens]:
    """Slå sammen ``funn`` til sekvenser, én gruppe per hendelsestype."""
    valg = valg or Segmenteringsvalg()

    per_type: dict[Hendelsestype, list[Funn]] = {}
    for f in funn:
        if f.score < valg.terskel(f.type):
            continue
        per_type.setdefault(f.type, []).append(f)

    sekvenser: list[Sekvens] = []
    for type_, treff in per_type.items():
        sekvenser.extend(_sekvenser_for_type(fil, type_, treff, valg, filvarighet))

    sekvenser.sort(key=lambda s: (s.start, s.type.value))
    return sekvenser


def _sekvenser_for_type(
    fil: Path,
    type_: Hendelsestype,
    treff: Sequence[Funn],
    valg: Segmenteringsvalg,
    filvarighet: float,
) -> list[Sekvens]:
    sortert = sorted(treff, key=lambda f: (f.start, f.slutt))

    grupper: list[list[Funn]] = []
    gruppeslutt = 0.0
    for f in sortert:
        if grupper and f.start - gruppeslutt <= valg.maks_hull:
            grupper[-1].append(f)
            gruppeslutt = max(gruppeslutt, f.slutt)
        else:
            grupper.append([f])
            gruppeslutt = f.slutt

    sekvenser: list[Sekvens] = []
    for gruppe in grupper:
        start = min(f.start for f in gruppe)
        slutt = max(f.slutt for f in gruppe)
        if slutt - start < valg.min_varighet:
            continue

        etiketter: dict[str, int] = {}
        for f in gruppe:
            if f.etikett:
                etiketter[f.etikett] = etiketter.get(f.etikett, 0) + 1

        sekvenser.append(
            Sekvens(
                fil=fil,
                type=type_,
                start=max(0.0, start - valg.padding),
                slutt=_begrens(slutt + valg.padding, filvarighet),
                score=max(f.score for f in gruppe),
                snittscore=sum(f.score for f in gruppe) / len(gruppe),
                antall_funn=len(gruppe),
                kilde=gruppe[0].kilde,
                etiketter=etiketter,
            )
        )

    return _slå_sammen_overlapp(sekvenser)


def _slå_sammen_overlapp(sekvenser: list[Sekvens]) -> list[Sekvens]:
    """Padding kan få nabosekvenser til å overlappe – slå dem i så fall sammen."""
    resultat: list[Sekvens] = []
    for sekvens in sorted(sekvenser, key=lambda s: s.start):
        if resultat and sekvens.start <= resultat[-1].slutt:
            forrige = resultat[-1]
            antall = forrige.antall_funn + sekvens.antall_funn
            forrige.snittscore = (
                forrige.snittscore * forrige.antall_funn + sekvens.snittscore * sekvens.antall_funn
            ) / max(1, antall)
            forrige.slutt = max(forrige.slutt, sekvens.slutt)
            forrige.score = max(forrige.score, sekvens.score)
            forrige.antall_funn = antall
            for navn, antall_treff in sekvens.etiketter.items():
                forrige.etiketter[navn] = forrige.etiketter.get(navn, 0) + antall_treff
        else:
            resultat.append(sekvens)
    return resultat


def utvid_punktfunn(funn: Iterable[Funn], varighet: float) -> list[Funn]:
    """Gi funn uten utstrekning (ett videobilde) varigheten de representerer."""
    utvidet: list[Funn] = []
    for f in funn:
        if f.slutt > f.start:
            utvidet.append(f)
            continue
        halv = varighet / 2.0
        utvidet.append(
            Funn(
                type=f.type,
                start=max(0.0, f.start - halv),
                slutt=f.start + halv,
                score=f.score,
                kilde=f.kilde,
                etikett=f.etikett,
            )
        )
    return utvidet


def _begrens(verdi: float, filvarighet: float) -> float:
    if filvarighet > 0:
        return min(verdi, filvarighet)
    return verdi


def slå_sammen_typer(sekvenser: Iterable[Sekvens], type_: Hendelsestype) -> list[Sekvens]:
    """Slå alle sekvenser (uansett type) sammen til ett felles spor.

    Nyttig når man bare vil ha «de delene der det skjer noe», ikke én
    sekvens per type.
    """
    per_fil: dict[Path, list[Sekvens]] = {}
    for sekvens in sekvenser:
        per_fil.setdefault(sekvens.fil, []).append(sekvens)

    samlet: list[Sekvens] = []
    for fil, gruppe in per_fil.items():
        omskrevet = [
            Sekvens(
                fil=fil,
                type=type_,
                start=s.start,
                slutt=s.slutt,
                score=s.score,
                snittscore=s.snittscore,
                antall_funn=s.antall_funn,
                kilde=s.kilde if all(a.kilde == s.kilde for a in gruppe) else Kilde.LYD,
                etiketter=dict(s.etiketter),
            )
            for s in gruppe
        ]
        samlet.extend(_slå_sammen_overlapp(omskrevet))

    samlet.sort(key=lambda s: (str(s.fil), s.start))
    return samlet
