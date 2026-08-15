"""Tester for coaching-agenten (kjører helt uten maskinvare/nett)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coach import (  # noqa: E402
    Agenda,
    AIAnalysator,
    Coach,
    Deltaker,
    Driver,
    Lagringssted,
    MinneLagring,
    MockOpptaker,
    Møteoppsett,
    Observasjoner,
    Opptak,
    Opptaksmodus,
    Opptaksstatus,
    ProfilArkiv,
    RegelbasertAnalysator,
    Situasjon,
    ØnsketUtkomme,
    forbered,
    kartlegg_drivere,
    lag_profil_id,
)


def _oppsett(**endringer) -> Møteoppsett:
    base = dict(
        situasjon=Situasjon.MØTE_JOBB,
        opplevd_rolle="teamdeltager",
        faktisk_rolle="møteleder",
        deltakere=[Deltaker(rolle="leder"), Deltaker(rolle="motstander")],
        agenda=Agenda.DISKUSJON,
        ønskede_utkommer=[ØnsketUtkomme.FELLES_EIERSKAP],
    )
    base.update(endringer)
    return Møteoppsett(**base)


# -- forberedelse -------------------------------------------------------
def test_kartlegg_drivere_gjenkjenner_kjente_roller():
    drivere = kartlegg_drivere(_oppsett())
    assert Driver.KONTROLL in drivere["leder"]
    assert Driver.RETTFERDIGHET in drivere["motstander"]


def test_ukjent_rolle_gir_nøytralt_utgangspunkt():
    drivere = kartlegg_drivere(_oppsett(deltakere=[Deltaker(rolle="nabo")]))
    assert drivere["nabo"] == [Driver.TRYGGHET, Driver.ANERKJENNELSE]


def test_forbered_gir_situasjons_agenda_og_dialogtips():
    forb = forbered(_oppsett())
    # Situasjonstips (møte på jobben) og agendatips (diskusjon) skal med.
    assert any("beslutning" in t for t in forb.møtetips)
    assert any("motpartens poeng" in t for t in forb.møtetips)
    # Dialogtips styrt av ønsket utfall (felles eierskap).
    assert any("forme løsningen" in t for t in forb.dialogtips)


def test_antall_personer_summerer_deltakere():
    oppsett = _oppsett(deltakere=[Deltaker(rolle="teamdeltager", antall=3), Deltaker(rolle="leder")])
    assert oppsett.antall_personer == 4


# -- opptak -------------------------------------------------------------
def test_opptak_start_stopp_lagrer_og_setter_status():
    coach = Coach(MockOpptaker(b"data"), MinneLagring(Lagringssted.MOBIL))
    økt = coach.ny_økt(_oppsett(), Opptak(modus=Opptaksmodus.LYD_OG_BILDE))

    coach.start_opptak(økt)
    assert økt.opptak.status == Opptaksstatus.TAR_OPP
    assert økt.opptak.startet is not None

    coach.stopp_opptak(økt, filnavn="test.mp4")
    assert økt.opptak.status == Opptaksstatus.FERDIG
    assert økt.opptak.lagringssted == Lagringssted.MOBIL
    assert økt.opptak.referanse == "minne://test.mp4"
    assert økt.opptak.varighet_sekunder is not None


def test_kan_ikke_stoppe_uten_pågående_opptak():
    coach = Coach(MockOpptaker(), MinneLagring())
    økt = coach.ny_økt(_oppsett())
    try:
        coach.stopp_opptak(økt)
    except RuntimeError:
        pass
    else:  # pragma: no cover
        raise AssertionError("forventet RuntimeError")


# -- analyse ------------------------------------------------------------
def test_analyse_peker_på_forbedringsområder():
    coach = Coach(MockOpptaker(), MinneLagring())
    økt = coach.ny_økt(_oppsett())
    obs = Observasjoner(
        min_taletid_andel=0.7,
        antall_avbrytelser_fra_meg=5,
        antall_apne_sporsmal=0,
        naadde_utkommer={ØnsketUtkomme.FELLES_EIERSKAP: False},
    )
    tb = coach.analyser(økt, obs)
    assert any("70 %" in f for f in tb.forbedringsområder)
    assert any("avbrøt 5" in f for f in tb.forbedringsområder)
    assert any("åpne spørsmål" in f for f in tb.forbedringsområder)
    assert tb.utkomme_vurdering[ØnsketUtkomme.FELLES_EIERSKAP] == "Ikke oppnådd ennå."


def test_analyse_gir_dialogtips_per_deltaker():
    coach = Coach(MockOpptaker(), MinneLagring())
    økt = coach.ny_økt(_oppsett())
    tb = coach.analyser(økt, Observasjoner())
    roller = {dt.rolle for dt in tb.per_deltaker}
    assert roller == {"leder", "motstander"}
    for dt in tb.per_deltaker:
        assert dt.forbedring_dialog  # hver ressurs får konkrete tips


# -- anonyme profiler ---------------------------------------------------
def test_profil_id_er_stabil_men_anonym():
    a = lag_profil_id("Kari fra salg", salt="s")
    b = lag_profil_id("kari fra salg", salt="s")
    c = lag_profil_id("Kari fra salg", salt="annet-salt")
    assert a == b            # samme kallenavn -> samme id
    assert a != c            # salt endrer id
    assert "kari" not in a.lower()  # ikke reversibelt til navnet


def test_arkiv_husker_og_akkumulerer_lærdom():
    arkiv = ProfilArkiv(salt="s")
    coach = Coach(MockOpptaker(), MinneLagring(), arkiv=arkiv)
    oppsett = _oppsett(deltakere=[Deltaker(rolle="leder", opplevd_relasjon="sjefen min")])

    økt = coach.ny_økt(oppsett)
    pid = oppsett.deltakere[0].profil_id
    assert pid is not None

    coach.analyser(økt, Observasjoner())
    profil = arkiv.hent(pid)
    assert profil is not None
    assert profil.typisk_rolle == "leder"
    assert profil.hendelser              # hendelse registrert
    assert profil.håndteringstips        # tips akkumulert
    # Aliaset er anonymt, ikke kallenavnet.
    assert "sjefen" not in profil.alias.lower()


def test_arkiv_lagres_og_lastes_fra_json(tmp_path):
    sti = tmp_path / "profiler.json"
    arkiv = ProfilArkiv(salt="s", sti=sti)
    p = arkiv.hent_eller_opprett("kunde X", rolle="kunde")
    arkiv.registrer_hendelse(p.profil_id, "møte", drivere=[Driver.TRYGGHET])
    arkiv.lagre()

    lastet = ProfilArkiv(salt="s", sti=sti)
    hentet = lastet.hent(p.profil_id)
    assert hentet is not None
    assert hentet.typisk_rolle == "kunde"
    assert Driver.TRYGGHET in hentet.antatte_drivere


# -- AI-analysator (uten nett, via falsk KI-klient) --------------------
class _FalskKlient:
    """Falsk KIKlient: fanger prompten og returnerer et fast JSON-svar."""

    def __init__(self, svar: dict):
        self.svar = svar
        self.sett_system = ""
        self.sett_bruker = ""
        self.sett_skjema: dict = {}

    def analyser_json(self, system, bruker, skjema):
        self.sett_system = system
        self.sett_bruker = bruker
        self.sett_skjema = skjema
        return self.svar


def test_ai_analysator_oversetter_json_til_tilbakemelding():
    svar = {
        "styrker": ["God lytting"],
        "forbedringsområder": ["Snakket for mye"],
        "per_deltaker": [
            {
                "rolle": "leder",
                "observerte_drivere": ["kontroll", "status"],
                "forbedring_dialog": ["Gi tydelige rammer"],
            }
        ],
        "utkomme_vurdering": [
            {"utkomme": "et større felles eierskap", "vurdering": "Delvis nådd"}
        ],
        "neste_øving": ["Øv på pauser"],
    }
    klient = _FalskKlient(svar)
    coach = Coach(MockOpptaker(), MinneLagring(), analysator=AIAnalysator(klient))
    økt = coach.ny_økt(_oppsett())

    tb = coach.analyser(økt, Observasjoner(transkripsjon="Hei, la oss starte..."))

    assert tb.styrker == ["God lytting"]
    assert tb.forbedringsområder == ["Snakket for mye"]
    (dt,) = tb.per_deltaker
    assert dt.rolle == "leder"
    assert dt.observerte_drivere == [Driver.KONTROLL, Driver.STATUS]
    assert tb.utkomme_vurdering[ØnsketUtkomme.FELLES_EIERSKAP] == "Delvis nådd"
    # Transkripsjonen og oppsettet skal ha nådd prompten.
    assert "Hei, la oss starte" in klient.sett_bruker
    assert "møte på jobben" in klient.sett_bruker


def test_ai_analysator_ignorerer_ugyldige_drivere():
    svar = {
        "styrker": [],
        "forbedringsområder": [],
        "per_deltaker": [
            {"rolle": "leder", "observerte_drivere": ["tull", "kontroll"], "forbedring_dialog": []}
        ],
        "utkomme_vurdering": [],
        "neste_øving": [],
    }
    coach = Coach(MockOpptaker(), MinneLagring(), analysator=AIAnalysator(_FalskKlient(svar)))
    økt = coach.ny_økt(_oppsett())
    tb = coach.analyser(økt, Observasjoner())
    (dt,) = tb.per_deltaker
    assert dt.observerte_drivere == [Driver.KONTROLL]  # "tull" hoppet over


def test_ai_analysator_faller_tilbake_ved_feil():
    class _Kræsjklient:
        def analyser_json(self, system, bruker, skjema):
            raise RuntimeError("nettverksfeil")

    analysator = AIAnalysator(_Kræsjklient(), reserve=RegelbasertAnalysator())
    coach = Coach(MockOpptaker(), MinneLagring(), analysator=analysator)
    økt = coach.ny_økt(_oppsett())
    # Skal ikke kaste – reserven (regelbasert) overtar.
    tb = coach.analyser(økt, Observasjoner(min_taletid_andel=0.7))
    assert any("70 %" in f for f in tb.forbedringsområder)


if __name__ == "__main__":
    import subprocess

    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", "-q", __file__]))
