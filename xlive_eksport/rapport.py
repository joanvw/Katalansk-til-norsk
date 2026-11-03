"""Filer som skrives ved siden av lydsporene.

* ``spor.csv``             – sporliste (fil, navn, X-Live-spor, kanal)
* ``markorer.csv``         – markører med tid og sampleposisjon
* ``markorer.mid``         – markører som MIDI-fil (Pro Tools, Logic,
                             Cubase m.fl. kan importere markører fra MIDI)
* ``<sesjon>.RPP``         – ferdig REAPER-prosjekt: spor navngitt, fader,
                             pan, farger og markører satt
* ``innstillinger.json``   – alle kanalinnstillinger maskinlesbart
* ``innstillinger.html``   – oversiktlig innstillingsark (gain, HPF, gate,
                             kompressor, EQ, FX, sends) for å stille inn
                             plugins i Pro Tools e.l.
* ``LES_MEG.txt``          – slik importerer du til Pro Tools / andre DAW-er
"""

from __future__ import annotations

import csv
import html
import json
import math
import os
import struct
from typing import Any

from .eksport import SporPlan
from .scene import FARGER, Kanal, Scene
from .sdkort import Sesjon


def tidskode(sekunder: float) -> str:
    ms = int(round(sekunder * 1000))
    t, ms = divmod(ms, 1000)
    return f"{t // 3600:02d}:{t // 60 % 60:02d}:{t % 60:02d}.{ms:03d}"


def _json_trygg(v: Any) -> Any:
    if isinstance(v, float) and math.isinf(v):
        return "-inf"
    if isinstance(v, dict):
        return {k: _json_trygg(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_json_trygg(x) for x in v]
    return v


# --------------------------------------------------------------------------

def skriv_sporliste(sti: str, planer: list[SporPlan]) -> None:
    with open(sti, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["nr", "fil", "navn", "type", "xlive_spor", "kilde", "digital_stillhet"])
        for p in planer:
            w.writerow([p.nr, "" if p.hoppet_over else p.filnavn, p.navn,
                        "stereo" if p.stereo else "mono",
                        "+".join(map(str, p.kilder)), " / ".join(p.etiketter),
                        "ja" if p.stille else "nei"])


def skriv_markorer_csv(sti: str, sesjon: Sesjon) -> None:
    with open(sti, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["nr", "navn", "tid", "sekunder", "sample"])
        for i, m in enumerate(sesjon.markorer, 1):
            w.writerow([i, f"Markør {i}", tidskode(m / sesjon.samplerate),
                        f"{m / sesjon.samplerate:.3f}", m])


def _vlq(n: int) -> bytes:
    ut = [n & 0x7F]
    n >>= 7
    while n:
        ut.append(0x80 | (n & 0x7F))
        n >>= 7
    return bytes(reversed(ut))


def skriv_markorer_midi(sti: str, sesjon: Sesjon) -> None:
    """MIDI type 0, 120 BPM, 960 PPQ → 1920 ticks per sekund."""
    ppq, ticks_per_s = 960, 1920
    hendelser = b"\x00\xff\x51\x03" + (500000).to_bytes(3, "big")
    # MIDI-tekst har ingen fast tegnkoding – hold det til ASCII.
    navn = sesjon.navn.encode("ascii", "replace")[:120]
    hendelser += b"\x00\xff\x03" + _vlq(len(navn)) + navn
    forrige = 0
    for i, m in enumerate(sesjon.markorer, 1):
        tick = int(round(m / sesjon.samplerate * ticks_per_s))
        tekst = f"Marker {i}".encode("ascii")
        hendelser += _vlq(tick - forrige) + b"\xff\x06" + _vlq(len(tekst)) + tekst
        forrige = tick
    hendelser += b"\x00\xff\x2f\x00"
    with open(sti, "wb") as f:
        f.write(b"MThd" + struct.pack(">IHHH", 6, 0, 1, ppq))
        f.write(b"MTrk" + struct.pack(">I", len(hendelser)) + hendelser)


# --------------------------------------------------------------------------
# REAPER
# --------------------------------------------------------------------------

def _db_til_lin(db: Any) -> float:
    if isinstance(db, bool) or not isinstance(db, (int, float)):
        return 1.0
    if math.isinf(db):
        return 0.0
    return 10 ** (db / 20)


def _reaper_farge(farge: str) -> int:
    hexv = FARGER.get(farge.removesuffix("i"))
    if not hexv or farge.startswith("OFF"):
        return 0
    r, g, b = int(hexv[1:3], 16), int(hexv[3:5], 16), int(hexv[5:7], 16)
    return (r | (g << 8) | (b << 16)) | 0x1000000


def _rpp_tekst(s: str) -> str:
    return '"' + s.replace('"', "'") + '"'


def skriv_reaper(sti: str, sesjon: Sesjon, planer: list[SporPlan],
                 bruk_fader: bool = True) -> None:
    lengde = sesjon.frames / sesjon.samplerate
    l = ["<REAPER_PROJECT 0.1 \"6.0\" 0",
         f"  SAMPLERATE {sesjon.samplerate} 0 0",
         f"  TITLE {_rpp_tekst(sesjon.navn)}"]
    for i, m in enumerate(sesjon.markorer, 1):
        l.append(f"  MARKER {i} {m / sesjon.samplerate:.6f} {_rpp_tekst(f'Markør {i}')} 0")
    for p in planer:
        if p.hoppet_over:
            continue
        k = p.kanaler[0]
        vol, pan, farge = 1.0, 0.0, 0
        if k is not None:
            if bruk_fader and k.mix:
                vol = _db_til_lin(k.mix.get("fader_db"))
                if not p.stereo and isinstance(k.mix.get("pan"), (int, float)):
                    pan = max(-1.0, min(1.0, k.mix["pan"] / 100))
            farge = _reaper_farge(k.farge)
        l += ["  <TRACK",
              f"    NAME {_rpp_tekst(p.navn)}",
              f"    PEAKCOL {farge}" if farge else "    PEAKCOL 16576",
              f"    VOLPAN {vol:.6f} {pan:.4f} -1 -1 1",
              f"    NCHAN 2",
              "    <ITEM",
              "      POSITION 0",
              f"      LENGTH {lengde:.6f}",
              f"      NAME {_rpp_tekst(p.navn)}",
              "      <SOURCE WAVE",
              f"        FILE {_rpp_tekst(p.filnavn)}",
              "      >",
              "    >",
              "  >"]
    l.append(">")
    with open(sti, "w", encoding="utf-8") as f:
        f.write("\n".join(l) + "\n")


# --------------------------------------------------------------------------
# Innstillinger
# --------------------------------------------------------------------------

def skriv_innstillinger_json(sti: str, sesjon: Sesjon, scene: Scene | None,
                             planer: list[SporPlan]) -> None:
    data: dict[str, Any] = {
        "sesjon": {"id": sesjon.id, "navn": sesjon.navn, "samplerate": sesjon.samplerate,
                   "kanaler": sesjon.kanaler, "bits_kilde": sesjon.bits,
                   "varighet_s": round(sesjon.varighet_s, 3),
                   "markorer_samples": sesjon.markorer},
        "kilde_for_innstillinger": scene.kilde if scene else None,
        "spor": [],
        "effekter": [],
    }
    for p in planer:
        data["spor"].append({
            "nr": p.nr, "fil": None if p.hoppet_over else p.filnavn, "navn": p.navn,
            "stereo": p.stereo, "xlive_spor": p.kilder, "kilde": p.etiketter,
            "kanaler": [k.som_dict() if k else None for k in p.kanaler],
        })
    if scene:
        data["chlink"] = scene.chlink
        data["routing"] = {"inn": scene.routing_inn, "kort": scene.routing_kort}
        data["effekter"] = [e.som_dict() for _, e in sorted(scene.effekter.items())]
    with open(sti, "w", encoding="utf-8") as f:
        json.dump(_json_trygg(data), f, ensure_ascii=False, indent=2)


def _fmt(v: Any, enhet: str = "") -> str:
    if v is None or v == "":
        return "–"
    if isinstance(v, bool):
        return "PÅ" if v else "AV"
    if isinstance(v, float):
        if math.isinf(v):
            return "-∞" + (f" {enhet}" if enhet else "")
        v = f"{v:g}"
    return f"{v}{(' ' + enhet) if enhet else ''}"


EQ_TYPER = {"LCut": "Lavkutt", "LShv": "Lav hylle", "PEQ": "Parametrisk",
            "VEQ": "Vintage", "HShv": "Høy hylle", "HCut": "Høykutt"}


def _kanal_html(k: Kanal) -> str:
    e = html.escape
    rader = []

    def rad(tittel: str, pa: Any, tekst: str) -> None:
        klasse = "pa" if pa is True else ("av" if pa is False else "")
        rader.append(f"<tr class='{klasse}'><th>{e(tittel)}</th>"
                     f"<td>{e(_fmt(pa)) if isinstance(pa, bool) else ''}</td><td>{tekst}</td></tr>")

    if k.headamp or k.preamp:
        deler = []
        if k.headamp:
            deler.append(f"Gain {_fmt(k.headamp.get('gain_db'), 'dB')}")
            deler.append(f"48V {_fmt(k.headamp.get('fantom'))}")
        if k.preamp:
            deler.append(f"Trim {_fmt(k.preamp.get('trim_db'), 'dB')}")
            deler.append(f"Fase snudd {_fmt(k.preamp.get('invert'))}")
        rad("Inngang", None, e(", ".join(deler)))
    if k.preamp:
        rad("Lavkutt (HPF)", k.preamp.get("lavkutt_pa"),
            e(f"{_fmt(k.preamp.get('lavkutt_hz'), 'Hz')}, "
              f"{_fmt(k.preamp.get('lavkutt_slope'), 'dB/okt')}"))
    if k.delay:
        rad("Delay", k.delay.get("pa"), e(_fmt(k.delay.get("ms"), "ms")))
    if k.gate:
        g = k.gate
        rad("Gate / ekspander", g.get("pa"), e(
            f"{_fmt(g.get('modus'))}, terskel {_fmt(g.get('terskel_db'), 'dB')}, "
            f"range {_fmt(g.get('range_db'), 'dB')}, attack {_fmt(g.get('attack_ms'), 'ms')}, "
            f"hold {_fmt(g.get('hold_ms'), 'ms')}, release {_fmt(g.get('release_ms'), 'ms')}"
            + (f"; key-filter {_fmt(k.gate_filter.get('type'))} "
               f"{_fmt(k.gate_filter.get('freq_hz'), 'Hz')}"
               if k.gate_filter.get("pa") else "")))
    if k.dyn:
        d = k.dyn
        rad("Kompressor", d.get("pa"), e(
            f"{_fmt(d.get('modus'))} {_fmt(d.get('detektor'))}/{_fmt(d.get('envelope'))}, "
            f"terskel {_fmt(d.get('terskel_db'), 'dB')}, ratio {_fmt(d.get('ratio'))}:1, "
            f"knee {_fmt(d.get('knee'))}, attack {_fmt(d.get('attack_ms'), 'ms')}, "
            f"hold {_fmt(d.get('hold_ms'), 'ms')}, release {_fmt(d.get('release_ms'), 'ms')}, "
            f"makeup {_fmt(d.get('makeup_db'), 'dB')}, mix {_fmt(d.get('mix_pct'), '%')}, "
            f"auto {_fmt(d.get('auto'))}, posisjon {_fmt(d.get('posisjon'))}"
            + (f"; sidechain-filter {_fmt(k.dyn_filter.get('type'))} "
               f"{_fmt(k.dyn_filter.get('freq_hz'), 'Hz')}"
               if k.dyn_filter.get("pa") else "")))
    if k.eq:
        band = "".join(
            f"<tr><td>{b.get('band')}</td><td>{e(EQ_TYPER.get(str(b.get('type')), _fmt(b.get('type'))))}</td>"
            f"<td>{e(_fmt(b.get('freq_hz'), 'Hz'))}</td><td>{e(_fmt(b.get('gain_db'), 'dB'))}</td>"
            f"<td>{e(_fmt(b.get('q')))}</td></tr>" for b in k.eq if b)
        rad("EQ", k.eq_pa, "<table class='eq'><tr><th>Bånd</th><th>Type</th><th>Frekvens</th>"
            f"<th>Gain</th><th>Q</th></tr>{band}</table>")
    if k.insert and k.insert.get("pa"):
        rad("Insert", True, e(f"{_fmt(k.insert.get('fx'))} ({_fmt(k.insert.get('posisjon'))})"))
    if k.mix:
        m = k.mix
        rad("Fader / pan", m.get("pa"), e(
            f"Fader {_fmt(m.get('fader_db'), 'dB')}, pan {_fmt(m.get('pan'))}, "
            f"LR {_fmt(m.get('lr'))}"))
    aktive = [(b, s) for b, s in sorted(k.sends.items())
              if s.get("pa") and isinstance(s.get("niva_db"), (int, float))
              and not math.isinf(s["niva_db"])]
    if aktive:
        rad("Sends", None, e(", ".join(f"Bus {b}: {_fmt(s['niva_db'], 'dB')}" for b, s in aktive)))
    return "<table class='strip'>" + "".join(rader) + "</table>"


def skriv_innstillinger_html(sti: str, sesjon: Sesjon, scene: Scene | None,
                             planer: list[SporPlan]) -> None:
    e = html.escape
    deler = [f"""<!doctype html><html lang="no"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Innstillinger – {e(sesjon.navn)}</title><style>
:root{{--bg:#fff;--fg:#1d1d1f;--mut:#6e6e73;--kant:#d2d2d7;--pa:#e8f5e9;--kort:#f7f7f9}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16161a;--fg:#f2f2f2;--mut:#a0a0a8;--kant:#38383f;--pa:#1d3322;--kort:#1f1f25}}}}
body{{font:14px/1.45 system-ui,sans-serif;background:var(--bg);color:var(--fg);margin:0;padding:16px;max-width:1100px;margin:auto}}
h1{{font-size:22px;margin:0 0 4px}} .mut{{color:var(--mut)}}
.spor{{background:var(--kort);border:1px solid var(--kant);border-radius:10px;padding:12px 14px;margin:14px 0;border-left:8px solid var(--farge)}}
.spor h2{{font-size:17px;margin:0 0 6px}} table{{border-collapse:collapse;width:100%}}
.strip th{{text-align:left;width:150px;vertical-align:top;padding:4px 8px 4px 0}}
.strip td{{padding:4px 6px;vertical-align:top;border-top:1px solid var(--kant)}}
.strip tr.pa td:nth-child(2){{color:#2e7d32;font-weight:600}} .strip tr.av td{{color:var(--mut)}}
.eq td,.eq th{{padding:2px 8px;border:1px solid var(--kant);font-weight:normal}}
@media print{{.spor{{break-inside:avoid}}}}
</style></head><body>
<h1>{e(sesjon.navn)}</h1>
<p class="mut">X-Live-sesjon {e(sesjon.id)} · {sesjon.kanaler} spor · {sesjon.samplerate} Hz ·
{e(tidskode(sesjon.varighet_s))} · innstillinger fra {e(scene.kilde if scene else 'ingen scene oppgitt')}</p>"""]
    if scene is None:
        deler.append("<p>Ingen scenefil/miksebord oppgitt – bare sporliste. "
                     "Bruk <code>--scene</code> eller <code>--miksebord</code> for EQ, kompressor og gate.</p>")
    for p in planer:
        farge = FARGER.get((p.kanaler[0].farge if p.kanaler[0] else "OFF").removesuffix("i"), "#888")
        tittel = f"{p.nr:02d} · {p.navn}" + (" (stereo)" if p.stereo else "")
        deler.append(f"<section class='spor' style='--farge:{farge}'><h2>{e(tittel)}</h2>"
                     f"<div class='mut'>{e(p.filnavn if not p.hoppet_over else 'ikke eksportert (stille)')}"
                     f" · X-Live-spor {'+'.join(map(str, p.kilder))} · {e(' / '.join(p.etiketter))}</div>")
        for k in p.kanaler:
            if k is not None:
                if p.stereo:
                    deler.append(f"<h3>{e(k.visningsnavn)} (kanal {k.nr})</h3>")
                deler.append(_kanal_html(k))
                if p.stereo and scene and scene.er_linket(k.nr):
                    break      # linkede kanaler deler innstillinger
        deler.append("</section>")
    if scene and scene.effekter:
        deler.append("<h2>Effekter (FX-rack)</h2><table class='strip'>")
        for _, fx in sorted(scene.effekter.items()):
            deler.append(f"<tr><th>FX {fx.nr}: {e(fx.type)}</th><td>kilde {e(' '.join(fx.kilde) or '–')}"
                         f"<br><span class='mut'>parametre: {e(' '.join(_fmt(v) for v in fx.parametre))}</span></td></tr>")
        deler.append("</table>")
    deler.append("</body></html>")
    with open(sti, "w", encoding="utf-8") as f:
        f.write("\n".join(deler))


LES_MEG = """Eksport fra X-Live: {navn}
{strek}

Lydfiler: {antall} spor, {sr} Hz, {bits} bit WAV. Alle filer starter på 0 og er
like lange – importer dem til starten av prosjektet, så ligger de synkront.
Stereospor er lagret som ekte stereo-WAV (L/R interleavet).

PRO TOOLS
  1. Lag en ny sesjon med {sr} Hz, 24 bit (eller 32-bit float).
  2. File > Import > Audio… (Shift+Cmd/Ctrl+I), merk alle .wav-filene,
     velg «Copy» / «Add» og «New Track», plassering «Session Start».
     Sporene får navn etter filene (01 Kick, 02 Snare …) i riktig rekkefølge.
  3. Markører: File > Import > MIDI… > markorer.mid, huk av for import av
     markører (Memory Locations). Ellers står tidene i markorer.csv.
  4. EQ, kompressor, gate og effekter: Pro Tools har ikke noe åpent format
     for å importere plugin-innstillinger, så de står i innstillinger.html
     (skriv ut eller ha den oppe ved siden av). Tilsvarende plugins:
       Lavkutt + EQ  -> EQ3 7-Band (HPF + 4 bånd)
       Gate          -> Dyn3 Expander/Gate
       Kompressor    -> Dyn3 Compressor/Limiter
       FX-rack       -> D-Verb / Mod Delay III e.l. på et Aux-spor
     innstillinger.json har alle verdiene maskinlesbart.

REAPER
  Åpne {rpp} – spornavn, farger, fader/pan og markører er satt.
  Markørene ligger også inne i hver WAV-fil (cue-markører).

ANDRE DAW-ER (Logic, Cubase, Studio One, Ableton, Luna …)
  Dra alle .wav-filene inn i et tomt prosjekt på posisjon 0.
  Markører: importer markorer.mid eller les tidene fra markorer.csv.
"""


def skriv_alt(utmappe: str, sesjon: Sesjon, scene: Scene | None,
              planer: list[SporPlan], bits: int) -> None:
    rpp = f"{_rens(sesjon.navn)}.RPP"
    skriv_sporliste(os.path.join(utmappe, "spor.csv"), planer)
    skriv_markorer_csv(os.path.join(utmappe, "markorer.csv"), sesjon)
    skriv_markorer_midi(os.path.join(utmappe, "markorer.mid"), sesjon)
    skriv_reaper(os.path.join(utmappe, rpp), sesjon, planer)
    skriv_innstillinger_json(os.path.join(utmappe, "innstillinger.json"), sesjon, scene, planer)
    skriv_innstillinger_html(os.path.join(utmappe, "innstillinger.html"), sesjon, scene, planer)
    tittel = f"Eksport fra X-Live: {sesjon.navn}"
    with open(os.path.join(utmappe, "LES_MEG.txt"), "w", encoding="utf-8") as f:
        f.write(LES_MEG.format(navn=sesjon.navn, strek="=" * len(tittel),
                               antall=sum(not p.hoppet_over for p in planer),
                               sr=sesjon.samplerate, bits=bits, rpp=rpp))


def _rens(navn: str) -> str:
    from .eksport import _rens_filnavn
    return _rens_filnavn(navn)
