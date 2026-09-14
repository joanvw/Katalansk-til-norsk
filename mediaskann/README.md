# mediaskann

Skann et **filområde** med video- og lydopptak, og få ut **tidskodede sekvenser**
der det er

- **mennesker i bildet**
- **lyd av mennesker** (tale, samtale, latter, gråt, rop, sang …)
- **dyr i bildet**
- **lyd av dyr** (bjeffing, mjauing, fuglesang, hest, ku, insekter …)

Resultatet kan leses som rapport (tekst/JSON/CSV) eller klippes rett ut til
egne filer.

Formater: alt ffmpeg kan lese – `avi`, `mp4`, `mkv`, `mov`, `mpg`, `webm`,
`wmv`, `mts` … og `mp3`, `wav`, `flac`, `m4a`, `aac`, `ogg`, `opus`.
Lydsporet i videofiler analyseres også.

## Bruk

```bash
# Se hva som finnes, uten å analysere
python -m mediaskann /opptak --liste

# Full skann med rapport
python -m mediaskann /opptak --json rapport.json --csv sekvenser.csv

# Bare menneskelyd og dyrelyd, klipp ut treffene
python -m mediaskann /opptak --typer stemme,dyrelyd --klipp utklipp/

# Hele løpet med simulerte data – uten ffmpeg og uten modeller
python -m mediaskann --demo
```

Utklippene havner i én mappe per type
(`utklipp/menneskestemme/`, `utklipp/dyr_synlig/` …), med sorterbare navn:
`intervju_menneskestemme_0000012.3-0000018.2.avi`.

Fra Python:

```python
from mediaskann import Skanner, FFmpegLeser, YamnetLyddetektor, YoloBildedetektor

skanner = Skanner(FFmpegLeser(), YamnetLyddetektor(), YoloBildedetektor())
resultat = skanner.skann_område("/opptak")

for sekvens in resultat.sekvenser:
    print(sekvens.fil.name, sekvens.type.etikett, sekvens.start, sekvens.slutt, sekvens.score)
```

## Hvordan det virker

1. **Filsøk** – finn mediefilene i området (rekursivt som standard).
2. **Lyd**: ffmpeg dekoder til 16 kHz mono, i biter, slik at lange filer ikke
   sprenger minnet. [YAMNet](https://tfhub.dev/google/yamnet/1) klassifiserer
   hvert 0,96-sekunds vindu mot AudioSets 521 klasser; klassene grupperes til
   *menneskelyd* og *dyrelyd* i `klasser.py`.
3. **Bilde**: ffmpeg trekker ut bilder (standard 1 per sekund), og en
   YOLO-modell finner `person` og COCOs ti dyreklasser.
4. **Segmentering** (`segmentering.py`) gjør de mange små funnene om til
   sekvenser: hold over terskel, tål korte opphold (`--maks-hull`), dropp
   glimt som er for korte (`--min-varighet`), legg på litt luft (`--padding`).
5. **Rapport og uttrekk** – JSON/CSV/tekst, og ffmpeg-klipp av hver sekvens.

## Skruer å vri på

| Valg | Standard | Hva det gjør |
| --- | --- | --- |
| `--typer` | alle | `menneske`, `stemme`, `dyr`, `dyrelyd`, `lyd`, `bilde`, `alle` |
| `--fps` | 1.0 | videobilder analysert per sekund – høyere = treffsikrere og tregere |
| `--terskel`, `--terskel-lyd`, `--terskel-bilde` | 0.30–0.40 | hvor sikker detektoren må være |
| `--min-varighet` | 0.8 s | korteste sekvens som beholdes |
| `--maks-hull` | 1.5 s | opphold som tåles inne i én sekvens |
| `--padding` | 0.5 s | luft i hver ende av sekvensen |
| `--nøyaktig` | av | klipp presist ved å kode om (tregere). Standard er raskt kopi-klipp, som starter på nærmeste nøkkelbilde |
| `--ikke-rekursivt` | av | ikke gå ned i undermapper |

Får du for mange treff: øk `--terskel` og `--min-varighet`. For få: senk
terskelen, og øk `--fps` for korte hendelser i bildet.

## Installasjon

ffmpeg gjør lesing og klipping:

```bash
apt install ffmpeg          # eller: brew install ffmpeg
```

Modellene er valgfrie – du kan kjøre bare lyd, bare bilde, eller begge:

```bash
pip install tensorflow tensorflow_hub   # lyd: mennesker og dyr (YAMNet)
pip install ultralytics pillow          # bilde: mennesker og dyr (YOLO)
pip install opencv-python               # bilde: kun mennesker (--bildemodell hog)
```

Mangler en av dem, sier CLI-en fra og fortsetter med den andre. Uten ffmpeg
kan bare PCM-WAV leses – da med standardbiblioteket alene. Modellvektene
lastes ned første gang; i et lukket miljø peker du `TFHUB_CACHE_DIR` mot en
ferdig nedlastet YAMNet og `--yolo-vekter` mot en lokal `.pt`-fil.

`--bildemodell hog` bruker OpenCVs innebygde HOG-detektor: ingen nedlasting,
men svakere, og den finner bare mennesker.

## Utvide

Kjernen er ren Python (standardbibliotek) og snakker bare med tre protokoller,
på samme måte som `dmx_spot_detect` snakker med `RDMTransport`:

- `Medieleser` – `finn_filer`, `les_info`, `les_lyd`, `les_rammer`, `klipp_ut`
- `Lyddetektor` – `analyser_lyd(fil, lydstrøm) -> list[Funn]`
- `Bildedetektor` – `analyser_rammer(fil, rammer) -> list[Funn]`

Vil du bruke en annen modell (f.eks. en egen trent dyredetektor, PANNs eller
en VAD), implementer protokollen og send den inn i `Skanner` – all
segmenterings-, rapport- og uttrekkslogikk gjenbrukes uendret. Funn skal ha
**absolutt tid i mediefilen**.

## Testing

```bash
python -m pytest tests/
```

Testene kjører mot `MockMedieleser` og mock-detektorer, og krever verken
ffmpeg, modeller eller ekte opptak.

## Vær klar over

- Deteksjonen er **statistisk**: den bommer begge veier. Bruk rapporten som
  en arbeidsliste, ikke som en fasit – særlig hvis noe skal slettes.
- Opptak av mennesker er personopplysninger. Skanning av et filområde med
  folk i lager en søkbar oversikt over hvor de er – ha et rettslig grunnlag
  for det, og slett utklipp du ikke trenger.
