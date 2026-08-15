"""Kommandolinje: kjør en komplett coaching-økt som demo.

Eksempel:
    python -m coach --demo     # kjør hele løpet med simulert opptak
"""

from __future__ import annotations

import argparse
import sys

from .analysis import Observasjoner
from .coach import Coach
from .models import (
    Deltaker,
    Møteoppsett,
    Opptak,
    Opptaksmodus,
)
from .profiles import ProfilArkiv
from .recorder import MinneLagring, MockOpptaker
from .situations import (
    Agenda,
    Møtested,
    Situasjon,
    ØnsketUtkomme,
)


def _demo_oppsett() -> Møteoppsett:
    return Møteoppsett(
        situasjon=Situasjon.MØTE_JOBB,
        opplevd_rolle="teamdeltager",
        faktisk_rolle="møteleder",
        deltakere=[
            Deltaker(rolle="leder", antall=1, opplevd_relasjon="litt anspent"),
            Deltaker(rolle="teamdeltager", antall=3),
            Deltaker(rolle="motstander", antall=1, opplevd_relasjon="uenig med meg"),
        ],
        agenda=Agenda.DISKUSJON,
        møtested=Møtested.PÅ_JOBB,
        ønskede_utkommer=[ØnsketUtkomme.FELLES_EIERSKAP, ØnsketUtkomme.BLI_SETT],
        notater="Ønsker å lande en beslutning uten å kjøre over noen.",
    )


def _skriv_forberedelse(forb) -> None:
    print("\n=== FØR TREFFET: forberedelse ===")
    print("Sannsynlige drivere i rommet:")
    for rolle, drivere in forb.sannsynlige_drivere.items():
        print(f"  - {rolle}: {', '.join(d.value for d in drivere)}")
    print("Møtetips:")
    for t in forb.møtetips:
        print(f"  • {t}")
    print("Dialogtips (mot dine ønskede utfall):")
    for t in forb.dialogtips:
        print(f"  • {t}")


def _skriv_tilbakemelding(tb) -> None:
    print("\n=== ETTER TREFFET: tilbakemelding ===")
    print("Styrker:")
    for s in tb.styrker:
        print(f"  + {s}")
    print("Forbedringsområder:")
    for f in tb.forbedringsområder:
        print(f"  ! {f}")
    print("Per ressurs i rommet:")
    for dt in tb.per_deltaker:
        drivere = ", ".join(d.value for d in dt.observerte_drivere)
        print(f"  - {dt.rolle} (drivere: {drivere})")
        for tips in dt.forbedring_dialog:
            print(f"      → {tips}")
    print("Vurdering av ønskede utfall:")
    for utkomme, vurdering in tb.utkomme_vurdering.items():
        print(f"  - {utkomme.value}: {vurdering}")
    print("Neste øving:")
    for n in tb.neste_øving:
        print(f"  ⇒ {n}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Coaching-agent (demo).")
    parser.add_argument(
        "--demo", action="store_true", help="Kjør en full økt med simulert opptak."
    )
    args = parser.parse_args(argv)

    if not args.demo:
        parser.print_help()
        return 0

    coach = Coach(
        opptaker=MockOpptaker(),
        lagringsmål=MinneLagring(),
        arkiv=ProfilArkiv(salt="demo-salt"),
    )

    oppsett = _demo_oppsett()
    økt = coach.ny_økt(oppsett, Opptak(modus=Opptaksmodus.LYD_OG_BILDE))
    _skriv_forberedelse(økt.forberedelse)

    coach.start_opptak(økt)
    coach.stopp_opptak(økt)
    print(f"\nOpptak lagret ({økt.opptak.lagringssted.value}): {økt.opptak.referanse}")

    # Litt observasjoner som om de kom fra transkripsjon/manuell logging.
    obs = Observasjoner(
        min_taletid_andel=0.68,
        antall_avbrytelser_fra_meg=4,
        antall_apne_sporsmal=1,
        taletid_per_deltaker={"motstander": 0.05, "teamdeltager": 0.2, "leder": 0.3},
        naadde_utkommer={ØnsketUtkomme.FELLES_EIERSKAP: False, ØnsketUtkomme.BLI_SETT: True},
    )
    tb = coach.analyser(økt, obs)
    _skriv_tilbakemelding(tb)

    print("\n=== ANONYME PROFILER (for trening over tid) ===")
    for profil in coach.arkiv.profiler.values():
        print(f"  {profil.alias} [{profil.profil_id}] – rolle: {profil.typisk_rolle}")
        for tips in profil.håndteringstips:
            print(f"      · {tips}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
