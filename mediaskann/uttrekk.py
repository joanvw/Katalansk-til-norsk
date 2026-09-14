"""Klipp de funne sekvensene ut til egne filer."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .media import Mediefeil, Medieleser
from .models import Mediefil, Sekvens

_UTRYGGE_TEGN = re.compile(r"[^\wÆØÅæøå.-]+")


@dataclass
class Utklipp:
    """En sekvens skrevet til egen fil."""

    sekvens: Sekvens
    sti: Path

    def som_dict(self) -> dict:
        return {**self.sekvens.som_dict(), "utklipp": str(self.sti)}


def trygt_navn(tekst: str) -> str:
    return _UTRYGGE_TEGN.sub("_", tekst).strip("_") or "fil"


def filnavn_for(sekvens: Sekvens, endelse: str | None = None) -> str:
    """``opptak_menneskestemme_000012.3-000018.7.wav`` – sorterbart og entydig."""
    suffiks = endelse if endelse is not None else sekvens.fil.suffix
    return (
        f"{trygt_navn(sekvens.fil.stem)}"
        f"_{sekvens.type.value}"
        f"_{sekvens.start:09.1f}-{sekvens.slutt:09.1f}"
        f"{suffiks}"
    )


def klipp_ut_sekvenser(
    leser: Medieleser,
    sekvenser: Iterable[Sekvens],
    målkatalog: Path | str,
    per_type: bool = True,
    nøyaktig: bool = False,
    logg: Callable[[str], None] | None = None,
) -> list[Utklipp]:
    """Skriv hver sekvens til ``målkatalog`` (eventuelt i undermappe per type).

    Feil på én sekvens stopper ikke resten – de logges og hoppes over.
    """
    logg = logg or (lambda melding: None)
    målkatalog = Path(målkatalog)
    målkatalog.mkdir(parents=True, exist_ok=True)

    info: dict[Path, Mediefil] = {}
    brukte: set[Path] = set()
    utklipp: list[Utklipp] = []

    for sekvens in sekvenser:
        if sekvens.fil not in info:
            try:
                info[sekvens.fil] = leser.les_info(sekvens.fil)
            except (Mediefeil, OSError) as exc:
                logg(f"Hopper over {sekvens.fil}: {exc}")
                continue
        mediefil = info[sekvens.fil]

        katalog = målkatalog / sekvens.type.value if per_type else målkatalog
        katalog.mkdir(parents=True, exist_ok=True)
        mål = _ledig_sti(katalog / filnavn_for(sekvens), brukte)

        try:
            skrevet = leser.klipp_ut(mediefil, sekvens.start, sekvens.slutt, mål, nøyaktig=nøyaktig)
        except (Mediefeil, OSError) as exc:
            logg(f"Klarte ikke klippe {sekvens.fil} {sekvens.start:.1f}s: {exc}")
            continue

        brukte.add(mål)
        utklipp.append(Utklipp(sekvens=sekvens, sti=Path(skrevet)))
        logg(f"Skrev {skrevet}")

    return utklipp


def _ledig_sti(ønsket: Path, brukte: set[Path]) -> Path:
    sti = ønsket
    teller = 2
    while sti in brukte or sti.exists():
        sti = ønsket.with_name(f"{ønsket.stem}_{teller}{ønsket.suffix}")
        teller += 1
    return sti
