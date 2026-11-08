# X-Live eksport – Behringer X32 / Midas M32

Kopierer **alle opptak** fra et X-Live SD-kort ut som **navngitte spor** klare
for Pro Tools, REAPER, Logic, Cubase og andre DAW-er, med **stereospor**,
markører og **EQ-, kompressor-, gate- og effektinnstillingene** fra miksebordet.

Kun Pythons standardbibliotek (Python 3.10+). Ingen installasjon av pakker.

## Kopiere via USB

Behringer/Midas har ikke laget X-Live-kortet slik at SD-kortene vises som disk
over USB-kabelen. Kortets USB-port er et 32×32 lydkort for opptak rett i DAW.
Kopiering via USB gjøres derfor slik:

1. Ta SD-kortet ut av X-Live-kortet og sett det i en **USB-kortleser**.
2. Start appen. Den finner kortet automatisk på alle USB-disker, og leter også
   etter scenefiler (`.scn`) på USB-pinnen fra miksebordets USB-port.
3. **Kopier råfiler først** (på som standard i vinduet, `--kopier-raa` på
   kommandolinjen): hele sesjonen kopieres urørt til `<målmappe>/Råfiler/`
   som sikkerhetskopi før sporene lages. Da kan SD-kortet tas ut så snart
   kopien er ferdig.
   * Avbrutt kopiering kan bare startes på nytt: ferdige filer hoppes over.
   * Hver fil skrives som `.del` og får riktig navn først når den er komplett
     og har riktig størrelse. `--verifiser` sammenligner i tillegg byte for byte.

```bash
python -m xlive_eksport usb                          # hva er koblet til?
python -m xlive_eksport kopier -o D:\Backup          # bare sikkerhetskopi
python -m xlive_eksport eksporter -o D:\Opptak --scene auto --kopier-raa
```

Uten mappe letes det automatisk på USB. `--scene auto` bruker nyeste
`.scn` på USB-pinnen.

## Kjøre på iPad

Vinduet (tkinter) finnes ikke på iPad, så der brukes en **veiviser** i
terminalen som spør steg for steg. Den starter automatisk.

**Dette trenger du**
* Appen **a-Shell** (gratis i App Store, har Python innebygd). Pythonista
  eller Pyto fungerer også.
* En **USB-C-kortleser** til SD-kortet (eller en USB-C-hub med kortleser).
* Helst en **ekstern SSD**: 32 spor × 2 timer i 24 bit er ca. 33 GB.
  Veiviseren sjekker ledig plass før den starter.

**Første gang**
1. Legg `xlive_eksport.pyz` i a-Shell-mappen: i Filer-appen ligger den under
   *På min iPad → a-Shell* (lagre den dit fra AirDrop, e-post eller iCloud
   Drive). Filen lages med `python -m xlive_eksport.bygg` på en datamaskin.
   * Alternativ: last ned repoet som ZIP fra GitHub i Safari, pakk ut i Filer,
     og bruk `python -m xlive_eksport` i den mappen i stedet.

**Hver gang**
1. Sett SD-kortet i kortleseren og koble den til iPaden.
2. Åpne a-Shell og skriv:
   ```
   pickFolder
   ```
   Velg SD-kortet i vinduet som dukker opp. Nå står du på kortet.
3. Start appen:
   ```
   python ~/Documents/xlive_eksport.pyz
   ```
4. Trykk Enter på spørsmålene for å bruke standardvalgene. Finnes det en
   `.scn`-fil på kortet eller i a-Shell-mappen, foreslås den automatisk (lagre
   scenen fra miksebordet til samme SD-kort eller en USB-pinne og kopier den over).
5. Sporene havner i mappen `X-Live eksport` på kortet (eller der du valgte).
   Åpne dem i Filer, i Logic Pro for iPad, Cubasis eller LumaFusion, eller
   flytt dem til maskinen med Pro Tools.

Tips: skriv `bookmark kort` etter `pickFolder`, så holder det med `jump kort`
neste gang.

## Kom i gang

```bash
python -m xlive_eksport            # grafisk vindu (velg kort, scene og målmappe)
python -m xlive_eksport veiviser   # spør steg for steg i terminalen (iPad)
```

eller fra kommandolinjen:

```bash
# Se hva som ligger på kortet
python -m xlive_eksport liste E:\

# Eksporter alt, med kanalnavn og innstillinger fra en scenefil
python -m xlive_eksport eksporter E:\ -o D:\Opptak --scene Konsert.scn

# … eller hent innstillingene rett fra miksebordet på nettverket
python -m xlive_eksport eksporter /Volumes/XLIVE -o ~/Opptak --miksebord 192.168.1.50

# Bare sesjon nr. 2, 32 bit, ekstra stereopar 31-32, dropp tomme spor
python -m xlive_eksport eksporter E:\ -o D:\Opptak -s 2 --bits 32 --stereo 31-32 --fjern-stille
```

## Hva du får (én mappe per sesjon)

| Fil | Innhold |
|---|---|
| `01 Kick.wav`, `02 Snare.wav`, … `17 Keys.wav` | Ett spor per kanal, navn fra miksebordet. Linkede kanaler blir én stereo-WAV. Alle starter på 0 og er like lange, så de ligger synkront i DAW-en. |
| `innstillinger.html` | Innstillingsark per spor: gain/48V, trim, fase, lavkutt, delay, gate, kompressor, 4-bånds EQ, insert, fader/pan, sends og FX-racket. |
| `innstillinger.json` | Det samme maskinlesbart. |
| `<sesjon>.RPP` | REAPER-prosjekt med spornavn, farger, fader, pan og markører. |
| `markorer.mid` / `markorer.csv` | Markørene fra X-Live (MIDI kan importeres som markører i Pro Tools m.fl.). Markørene ligger også inne i hver WAV (cue-markører). |
| `spor.csv` | Sporliste: fil → X-Live-spor → kanal. |
| `LES_MEG.txt` | Steg for steg-import til Pro Tools og andre DAW-er. |

## Kanalnavn og innstillinger

X-Live-kortet lagrer **bare lyd og markører**. Navn, EQ, dynamikk og FX må
hentes fra miksebordet på én av to måter:

1. **Scenefil** – lagre scenen til USB-pinne på miksebordet (helst under
   konserten), og pek på `.scn`-filen med `--scene`.
2. **Direkte over nettverk** – `--miksebord <IP>` henter dagens innstillinger
   via OSC (port 10023). Gir innstillingene *nå*, ikke nødvendigvis slik de var
   under opptaket.

Appen følger routingen (kort-utganger → inngangsblokker → kanalens kilde), så
navnene blir riktige også om kortet tar opp fra AES50/S16 eller ved virtual
soundcheck. Mangler routing, antas spor N = kanal N. Navn kan overstyres med
`--navn navn.txt` (én linje per spor: `5;Vokal Kari`).

### Pro Tools og plugin-innstillinger

Pro Tools har ikke noe åpent format for å importere plugin-innstillinger, så
EQ/komp/gate kan ikke legges inn automatisk. `innstillinger.html` er laget
for å stille inn tilsvarende plugins raskt (EQ3 7-Band, Dyn3
Compressor/Limiter, Dyn3 Expander/Gate). `innstillinger.json` kan brukes
hvis du vil skrive egen konvertering.

## Formater

* Kortets 8/16/32 kanaler, 44,1/48 kHz, 32-bit WAV. Takes på ~4 GB
  (`00000001.WAV`, `00000002.WAV` …) limes sammen sømløst.
* Standard ut er **24 bit** (Pro Tools-vennlig); `--bits 32` eller `samme`
  beholder originalen.
* Filer over 4 GB skrives automatisk som RF64.
* Tåler opptak der kortet ble tatt ut / strømmen gikk (ufullstendig WAV-header).

## Kjent usikkerhet

`SE_LOG.BIN` er ikke dokumentert av Behringer. Markører (offset 1052) og
sesjonsnavn (offset 1552) leses etter oppsettet som er kartlagt av miljøet
(bl.a. Patrick-Gilles Maillots X32-verktøy). Lydformat og lengde hentes alltid
fra WAV-filene selv.

## Tester

```bash
python -m pytest tests/test_xlive_eksport.py
```
