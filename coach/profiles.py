"""Anonymisert profilarkiv – husk personer uten å lagre identiteten.

Målet er å kunne trene på håndteringen av *relasjoner* over tid.
Arkivet lagrer derfor aldri navn eller annet identifiserende. Du gir et
lokalt kallenavn (kjent bare for deg), og arkivet lager en stabil,
anonym ``profil_id`` ved å hashe kallenavnet med et hemmelig «salt».
Selve kallenavnet lagres ikke – bare et generert alias som «Kollega A».
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import Driver, Profil


def lag_profil_id(kallenavn: str, salt: str) -> str:
    """Stabil, anonym id fra et privat kallenavn + hemmelig salt.

    Samme kallenavn gir samme id (så du kan slå opp igjen), men id-en kan
    ikke reverseres til kallenavnet uten saltet.
    """
    material = f"{salt}:{kallenavn.strip().lower()}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:16]


def _alias(rolle: str, nummer: int) -> str:
    grunn = rolle.strip().capitalize() or "Person"
    bokstav = chr(ord("A") + (nummer % 26))
    return f"{grunn} {bokstav}"


class ProfilArkiv:
    """Enkelt JSON-basert arkiv over anonymiserte profiler.

    Uten ``sti`` holdes alt i minnet (fint for tester/demo). Med ``sti``
    lastes og lagres arkivet som JSON, f.eks. i mobilappens dokumentområde
    eller på en valgt lagringsplattform.
    """

    def __init__(self, salt: str, sti: str | Path | None = None):
        self.salt = salt
        self.sti = Path(sti) if sti else None
        self.profiler: dict[str, Profil] = {}
        if self.sti and self.sti.exists():
            self._last()

    # -- oppslag / opprettelse ------------------------------------------
    def hent_eller_opprett(self, kallenavn: str, rolle: str = "") -> Profil:
        """Finn profilen for et kallenavn, eller opprett en ny anonym profil."""
        profil_id = lag_profil_id(kallenavn, self.salt)
        profil = self.profiler.get(profil_id)
        if profil is None:
            profil = Profil(
                profil_id=profil_id,
                alias=_alias(rolle, len(self.profiler)),
                typisk_rolle=rolle,
            )
            self.profiler[profil_id] = profil
        return profil

    def hent(self, profil_id: str) -> Profil | None:
        return self.profiler.get(profil_id)

    # -- oppdatering ----------------------------------------------------
    def registrer_hendelse(
        self,
        profil_id: str,
        hendelse: str,
        drivere: list[Driver] | None = None,
        håndteringstips: list[str] | None = None,
    ) -> Profil:
        """Legg til lærdom fra en økt i profilens historikk."""
        profil = self.profiler[profil_id]
        profil.hendelser.append(hendelse)
        for d in drivere or ():
            if d not in profil.antatte_drivere:
                profil.antatte_drivere.append(d)
        for tips in håndteringstips or ():
            if tips not in profil.håndteringstips:
                profil.håndteringstips.append(tips)
        return profil

    # -- lagring --------------------------------------------------------
    def lagre(self) -> None:
        if not self.sti:
            return
        self.sti.parent.mkdir(parents=True, exist_ok=True)
        self.sti.write_text(self._til_json(), encoding="utf-8")

    def _til_json(self) -> str:
        data = {
            pid: {
                "profil_id": p.profil_id,
                "alias": p.alias,
                "typisk_rolle": p.typisk_rolle,
                "antatte_drivere": [d.name for d in p.antatte_drivere],
                "hendelser": p.hendelser,
                "håndteringstips": p.håndteringstips,
            }
            for pid, p in self.profiler.items()
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _last(self) -> None:
        assert self.sti is not None
        rå = json.loads(self.sti.read_text(encoding="utf-8"))
        for pid, d in rå.items():
            self.profiler[pid] = Profil(
                profil_id=d["profil_id"],
                alias=d["alias"],
                typisk_rolle=d.get("typisk_rolle", ""),
                antatte_drivere=[Driver[n] for n in d.get("antatte_drivere", [])],
                hendelser=list(d.get("hendelser", [])),
                håndteringstips=list(d.get("håndteringstips", [])),
            )
