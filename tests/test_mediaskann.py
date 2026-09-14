"""Tester for mediaskann – kjører uten ffmpeg, modeller eller ekte opptak."""

import json
import os
import sys
import wave
from array import array
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mediaskann import (  # noqa: E402
    Bilderamme,
    FFmpegLeser,
    Funn,
    Hendelsestype,
    Kilde,
    Lydstrøm,
    Mediefil,
    MockBildedetektor,
    MockLyddetektor,
    MockMedieleser,
    Segmenteringsvalg,
    Skanner,
    Skannvalg,
    bildetype,
    filnavn_for,
    finn_mediefiler,
    klipp_ut_sekvenser,
    lag_sekvenser,
    lydtype,
    skriv_csv,
    skriv_json,
    slå_sammen_typer,
    tekstrapport,
    tidskode,
    utvid_punktfunn,
)
from mediaskann.__main__ import main  # noqa: E402

FIL = Path("/opptak/intervju.avi")


def lydfunn(start, slutt, type_=Hendelsestype.MENNESKESTEMME, score=0.8, etikett="Speech"):
    return Funn(type=type_, start=start, slutt=slutt, score=score, kilde=Kilde.LYD, etikett=etikett)


# --- filsøk ----------------------------------------------------------------
def test_finn_mediefiler_filtrerer_og_gaar_i_dybden(tmp_path):
    (tmp_path / "under").mkdir()
    for navn in ["a.avi", "b.mp3", "c.txt", "under/d.wav", "under/e.doc"]:
        (tmp_path / navn).write_bytes(b"")

    funnet = [p.name for p in finn_mediefiler(tmp_path)]
    assert funnet == ["a.avi", "b.mp3", "d.wav"]

    grunt = [p.name for p in finn_mediefiler(tmp_path, rekursivt=False)]
    assert grunt == ["a.avi", "b.mp3"]


def test_finn_mediefiler_tar_enkeltfil(tmp_path):
    fil = tmp_path / "opptak.wav"
    fil.write_bytes(b"")
    assert finn_mediefiler(fil) == [fil]


# --- klassekart ------------------------------------------------------------
def test_klasser_kartlegges_til_hendelsestyper():
    assert lydtype("Speech") is Hendelsestype.MENNESKESTEMME
    assert lydtype("baby cry, infant cry") is Hendelsestype.MENNESKESTEMME
    assert lydtype("Bark") is Hendelsestype.DYRELYD
    assert lydtype("Bird vocalization, bird call, bird song") is Hendelsestype.DYRELYD
    assert lydtype("Chainsaw") is None

    assert bildetype("person") is Hendelsestype.MENNESKE_SYNLIG
    assert bildetype("dog") is Hendelsestype.DYR_SYNLIG
    assert bildetype("bicycle") is None


# --- segmentering ----------------------------------------------------------
def test_sekvenser_slaas_sammen_over_smaa_hull():
    valg = Segmenteringsvalg(maks_hull=1.0, min_varighet=0.5, padding=0.0)
    funn = [lydfunn(0.0, 1.0), lydfunn(1.5, 2.5), lydfunn(10.0, 12.0)]

    sekvenser = lag_sekvenser(FIL, funn, valg, filvarighet=60.0)

    assert [(s.start, s.slutt) for s in sekvenser] == [(0.0, 2.5), (10.0, 12.0)]
    assert sekvenser[0].antall_funn == 2


def test_funn_under_terskel_forkastes():
    valg = Segmenteringsvalg(
        terskler={Hendelsestype.MENNESKESTEMME: 0.5}, min_varighet=0.5, padding=0.0
    )
    funn = [lydfunn(0.0, 2.0, score=0.4), lydfunn(5.0, 7.0, score=0.9)]

    sekvenser = lag_sekvenser(FIL, funn, valg)

    assert len(sekvenser) == 1
    assert sekvenser[0].start == 5.0


def test_for_korte_sekvenser_forkastes():
    valg = Segmenteringsvalg(min_varighet=2.0, padding=0.0, maks_hull=0.1)
    funn = [lydfunn(0.0, 0.5), lydfunn(5.0, 8.0)]

    sekvenser = lag_sekvenser(FIL, funn, valg)

    assert [(s.start, s.slutt) for s in sekvenser] == [(5.0, 8.0)]


def test_padding_begrenses_av_filens_lengde():
    valg = Segmenteringsvalg(min_varighet=0.5, padding=2.0, maks_hull=0.1)
    funn = [lydfunn(0.5, 3.0), lydfunn(28.0, 29.5)]

    sekvenser = lag_sekvenser(FIL, funn, valg, filvarighet=30.0)

    assert sekvenser[0].start == 0.0  # ikke negativ
    assert sekvenser[-1].slutt == 30.0  # ikke forbi filslutt


def test_overlappende_sekvenser_etter_padding_slaas_sammen():
    valg = Segmenteringsvalg(min_varighet=0.5, padding=1.0, maks_hull=0.5)
    funn = [lydfunn(0.0, 1.0, score=0.6), lydfunn(2.0, 3.0, score=0.9)]

    sekvenser = lag_sekvenser(FIL, funn, valg, filvarighet=60.0)

    assert len(sekvenser) == 1
    assert (sekvenser[0].start, sekvenser[0].slutt) == (0.0, 4.0)
    assert sekvenser[0].score == 0.9
    assert sekvenser[0].antall_funn == 2


def test_typer_segmenteres_hver_for_seg():
    valg = Segmenteringsvalg(min_varighet=0.5, padding=0.0, maks_hull=1.0)
    funn = [
        lydfunn(0.0, 2.0, Hendelsestype.MENNESKESTEMME),
        lydfunn(0.5, 2.5, Hendelsestype.DYRELYD, etikett="Bark"),
    ]

    sekvenser = lag_sekvenser(FIL, funn, valg)

    assert {s.type for s in sekvenser} == {Hendelsestype.MENNESKESTEMME, Hendelsestype.DYRELYD}


def test_etiketter_telles_opp():
    valg = Segmenteringsvalg(min_varighet=0.5, padding=0.0, maks_hull=1.0)
    funn = [
        lydfunn(0.0, 1.0, etikett="Speech"),
        lydfunn(1.0, 2.0, etikett="Speech"),
        lydfunn(2.0, 3.0, etikett="Laughter"),
    ]

    sekvens = lag_sekvenser(FIL, funn, valg)[0]

    assert sekvens.etiketter == {"Speech": 2, "Laughter": 1}
    assert sekvens.toppetiketter[0] == "Speech"


def test_punktfunn_fra_videobilder_faar_varighet():
    punkt = Funn(
        type=Hendelsestype.MENNESKE_SYNLIG,
        start=10.0,
        slutt=10.0,
        score=0.9,
        kilde=Kilde.BILDE,
        etikett="person",
    )

    utvidet = utvid_punktfunn([punkt], 1.0)[0]

    assert (utvidet.start, utvidet.slutt) == (9.5, 10.5)


def test_slaa_sammen_typer_gir_ett_felles_spor():
    valg = Segmenteringsvalg(min_varighet=0.5, padding=0.0, maks_hull=0.5)
    funn = [
        lydfunn(0.0, 3.0, Hendelsestype.MENNESKESTEMME),
        lydfunn(2.0, 5.0, Hendelsestype.DYRELYD, etikett="Bark"),
    ]
    sekvenser = lag_sekvenser(FIL, funn, valg)

    samlet = slå_sammen_typer(sekvenser, Hendelsestype.MENNESKESTEMME)

    assert len(samlet) == 1
    assert (samlet[0].start, samlet[0].slutt) == (0.0, 5.0)


def test_tidskode_formatteres_som_ffmpeg_vil_ha_det():
    assert tidskode(0) == "00:00:00.000"
    assert tidskode(3725.5) == "01:02:05.500"
    assert tidskode(-4) == "00:00:00.000"


# --- skanning ---------------------------------------------------------------
def _oppsett():
    video = Mediefil(sti=FIL, varighet=60.0, har_lyd=True, har_video=True, format="avi")
    leser = MockMedieleser()
    leser.legg_til(
        video,
        lyd=Lydstrøm(prøver=array("f", [0.0] * 16000), samplerate=16000),
        rammer=[Bilderamme(tid=float(t), data=b"") for t in range(60)],
    )
    lyd = MockLyddetektor({str(FIL): [lydfunn(2.0 + t, 3.0 + t) for t in range(0, 6)]})
    bilde = MockBildedetektor(
        {
            str(FIL): [
                Funn(
                    type=Hendelsestype.MENNESKE_SYNLIG,
                    start=float(t),
                    slutt=float(t),
                    score=0.9,
                    kilde=Kilde.BILDE,
                    etikett="person",
                )
                for t in range(30, 36)
            ]
        }
    )
    return leser, lyd, bilde


def test_skanner_finner_sekvenser_i_bade_lyd_og_bilde():
    leser, lyd, bilde = _oppsett()

    resultat = Skanner(leser, lyd, bilde).skann_område(Path("/opptak"))

    typer = {s.type for s in resultat.sekvenser}
    assert typer == {Hendelsestype.MENNESKESTEMME, Hendelsestype.MENNESKE_SYNLIG}
    assert resultat.filer[0].feil == ""


def test_skanner_respekterer_valgte_typer():
    leser, lyd, bilde = _oppsett()
    valg = Skannvalg(typer=frozenset({Hendelsestype.MENNESKESTEMME}))

    resultat = Skanner(leser, lyd, bilde, valg=valg).skann_område(Path("/opptak"))

    assert {s.type for s in resultat.sekvenser} == {Hendelsestype.MENNESKESTEMME}


def test_skanner_uten_lyddetektor_gir_merknad():
    leser, _, bilde = _oppsett()

    resultat = Skanner(leser, None, bilde).skann_område(Path("/opptak"))

    assert any("lyddetektor" in m for m in resultat.filer[0].merknader)
    assert {s.type for s in resultat.sekvenser} == {Hendelsestype.MENNESKE_SYNLIG}


def test_feil_paa_en_fil_stopper_ikke_skanningen():
    leser, lyd, bilde = _oppsett()

    filresultat = Skanner(leser, lyd, bilde).skann_fil(Path("/opptak/finnes-ikke.avi"))

    assert filresultat.feil
    assert filresultat.sekvenser == []


# --- rapport ---------------------------------------------------------------
def test_json_og_csv_skrives(tmp_path):
    leser, lyd, bilde = _oppsett()
    resultat = Skanner(leser, lyd, bilde).skann_område(Path("/opptak"))

    json_sti = skriv_json(resultat, tmp_path / "rapport.json")
    csv_sti = skriv_csv(resultat.sekvenser, tmp_path / "sekvenser.csv")

    data = json.loads(json_sti.read_text(encoding="utf-8"))
    assert data["antall_sekvenser"] == len(resultat.sekvenser)
    assert data["sekvenser"][0]["start_tidskode"].startswith("00:00:")

    linjer = csv_sti.read_text(encoding="utf-8").strip().splitlines()
    assert linjer[0].startswith("fil,type,beskrivelse")
    assert len(linjer) == len(resultat.sekvenser) + 1


def test_tekstrapport_oppsummerer():
    leser, lyd, bilde = _oppsett()
    resultat = Skanner(leser, lyd, bilde).skann_område(Path("/opptak"))

    tekst = tekstrapport(resultat)

    assert "Sekvenser funnet:" in tekst
    assert "lyd av mennesker" in tekst


# --- uttrekk ---------------------------------------------------------------
def test_filnavn_er_sorterbart_og_beskrivende():
    sekvens = lag_sekvenser(
        FIL, [lydfunn(12.3, 18.2)], Segmenteringsvalg(min_varighet=0.5, padding=0.0)
    )[0]

    navn = filnavn_for(sekvens)

    assert navn == "intervju_menneskestemme_0000012.3-0000018.2.avi"


def test_utklipp_legges_i_mappe_per_type(tmp_path):
    leser, lyd, bilde = _oppsett()
    resultat = Skanner(leser, lyd, bilde).skann_område(Path("/opptak"))

    utklipp = klipp_ut_sekvenser(leser, resultat.sekvenser, tmp_path)

    assert len(utklipp) == len(resultat.sekvenser)
    assert {u.sti.parent.name for u in utklipp} == {"menneskestemme", "menneske_synlig"}
    assert [k[0] for k in leser.utklipp] == [FIL] * len(utklipp)


def test_utklipp_kan_legges_flatt(tmp_path):
    leser, lyd, bilde = _oppsett()
    resultat = Skanner(leser, lyd, bilde).skann_område(Path("/opptak"))

    utklipp = klipp_ut_sekvenser(leser, resultat.sekvenser, tmp_path, per_type=False)

    assert {u.sti.parent for u in utklipp} == {tmp_path}


# --- WAV uten ffmpeg --------------------------------------------------------
def _lag_wav(sti: Path, sekunder: float = 1.0, samplerate: int = 32000) -> Path:
    with wave.open(str(sti), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(samplerate)
        f.writeframes(b"\x00\x10" * int(samplerate * sekunder))
    return sti


def test_wav_leses_uten_ffmpeg(tmp_path):
    sti = _lag_wav(tmp_path / "opptak.wav", sekunder=2.0)
    leser = FFmpegLeser(ffmpeg="finnes-ikke-ffmpeg", ffprobe="finnes-ikke-ffprobe")

    info = leser.les_info(sti)
    assert info.har_lyd and not info.har_video
    assert abs(info.varighet - 2.0) < 0.01

    biter = list(leser.les_lyd(info, samplerate=16000, bit_sekunder=1.0))
    assert len(biter) == 2
    assert biter[0].samplerate == 16000
    assert abs(biter[0].varighet - 1.0) < 0.05
    assert biter[1].start == 1.0


def test_ukjent_format_uten_ffmpeg_gir_tydelig_feil(tmp_path):
    sti = tmp_path / "opptak.mp3"
    sti.write_bytes(b"ikke en ekte mp3")
    leser = FFmpegLeser(ffmpeg="finnes-ikke-ffmpeg", ffprobe="finnes-ikke-ffprobe")

    resultat = Skanner(leser, MockLyddetektor(), None).skann_fil(sti)

    assert "ffmpeg" in resultat.feil


# --- kommandolinje ----------------------------------------------------------
def test_cli_demo_kjoerer(capsys):
    assert main(["--demo", "--stille"]) == 0
    utdata = capsys.readouterr().out
    assert "Sekvenser funnet:" in utdata
    assert "lyd av dyr" in utdata


def test_cli_demo_med_typevalg(capsys):
    assert main(["--demo", "--stille", "--typer", "dyrelyd"]) == 0
    utdata = capsys.readouterr().out
    assert "lyd av dyr" in utdata
    assert "mennesker i bildet" not in utdata


def test_cli_demo_skriver_rapportfiler(tmp_path, capsys):
    kode = main(
        [
            "--demo",
            "--stille",
            "--json", str(tmp_path / "rapport.json"),
            "--csv", str(tmp_path / "sekvenser.csv"),
            "--klipp", str(tmp_path / "utklipp"),
        ]
    )
    capsys.readouterr()

    assert kode == 0
    assert (tmp_path / "rapport.json").exists()
    assert (tmp_path / "sekvenser.csv").exists()


def test_cli_uten_omraade_feiler(capsys):
    try:
        main(["--stille"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("forventet SystemExit")


def test_cli_lister_filer(tmp_path, capsys):
    (tmp_path / "a.avi").write_bytes(b"")
    (tmp_path / "notat.txt").write_bytes(b"")

    assert main([str(tmp_path), "--liste", "--stille"]) == 0

    utdata = capsys.readouterr().out
    assert "a.avi" in utdata
    assert "notat.txt" not in utdata
