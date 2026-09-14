"""Rapportering: JSON, CSV og en lesbar oppsummering for terminalen."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .models import Hendelsestype, Sekvens, Skannresultat, tidskode

CSV_KOLONNER = [
    "fil",
    "type",
    "beskrivelse",
    "kilde",
    "start",
    "slutt",
    "varighet",
    "start_tidskode",
    "slutt_tidskode",
    "score",
    "snittscore",
    "antall_funn",
    "etiketter",
]


def som_json(resultat: Skannresultat) -> dict:
    return {"skannet": datetime.now().astimezone().isoformat(timespec="seconds"), **resultat.som_dict()}


def skriv_json(resultat: Skannresultat, sti: Path | str) -> Path:
    sti = Path(sti)
    sti.parent.mkdir(parents=True, exist_ok=True)
    sti.write_text(json.dumps(som_json(resultat), ensure_ascii=False, indent=2), encoding="utf-8")
    return sti


def skriv_csv(sekvenser: Iterable[Sekvens], sti: Path | str) -> Path:
    sti = Path(sti)
    sti.parent.mkdir(parents=True, exist_ok=True)
    with sti.open("w", newline="", encoding="utf-8") as f:
        skriver = csv.DictWriter(f, fieldnames=CSV_KOLONNER)
        skriver.writeheader()
        for sekvens in sekvenser:
            rad = sekvens.som_dict()
            rad["etiketter"] = ", ".join(rad["etiketter"][:5])
            skriver.writerow({kolonne: rad[kolonne] for kolonne in CSV_KOLONNER})
    return sti


def tekstrapport(resultat: Skannresultat, maks_per_fil: int = 0) -> str:
    """Lesbar oppsummering – det CLI-en skriver ut."""
    linjer: list[str] = []
    sekvenser = resultat.sekvenser
    linjer.append(f"Filområde: {resultat.rot}")
    linjer.append(f"Filer analysert: {len(resultat.filer)}")
    linjer.append(f"Sekvenser funnet: {len(sekvenser)}")

    for type_ in Hendelsestype:
        treff = [s for s in sekvenser if s.type is type_]
        if treff:
            samlet = sum(s.varighet for s in treff)
            linjer.append(f"  - {type_.etikett}: {len(treff)} stk, til sammen {samlet:.1f} s")
    linjer.append("")

    for filresultat in resultat.filer:
        overskrift = f"{filresultat.mediefil.sti} ({filresultat.mediefil.varighet:.1f} s)"
        linjer.append(overskrift)
        if filresultat.feil:
            linjer.append(f"    FEIL: {filresultat.feil}")
        for merknad in filresultat.merknader:
            linjer.append(f"    merknad: {merknad}")
        if not filresultat.sekvenser and not filresultat.feil:
            linjer.append("    (ingen treff)")

        vis = filresultat.sekvenser
        if maks_per_fil > 0:
            vis = vis[:maks_per_fil]
        for sekvens in vis:
            etiketter = ", ".join(sekvens.toppetiketter[:3])
            linjer.append(
                f"    {tidskode(sekvens.start)} – {tidskode(sekvens.slutt)}"
                f"  {sekvens.type.etikett:<18} score {sekvens.score:.2f}"
                + (f"  [{etiketter}]" if etiketter else "")
            )
        skjult = len(filresultat.sekvenser) - len(vis)
        if skjult > 0:
            linjer.append(f"    … og {skjult} til")
        linjer.append("")

    return "\n".join(linjer).rstrip() + "\n"
