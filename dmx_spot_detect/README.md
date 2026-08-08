# dmx_spot_detect

Oppdag og klassifiser hvilke **spottere/armaturer som er koblet til en DMX-linje**.

## Viktig: DMX vs. RDM

Rent **DMX512 er enveis** – kontrolleren sender data til armaturene uten å få
noe tilbake. Det finnes derfor *ingen* måte å auto-detektere koblede armaturer
på med ren DMX.

Det som faktisk kan oppdage og identifisere enheter er **RDM (Remote Device
Management, ANSI E1.20)**, som kjører på samme kabel/kontakt. Denne pakken
bruker RDM til å:

1. **oppdage** alle enheter på linjen (RDM discovery → liste med UID-er),
2. lese **`DEVICE_INFO`** fra hver enhet, og
3. **klassifisere** typen via det standardiserte feltet *Product Category*
   (moving head, fast spotter/PAR, scanner, hazer, dimmer osv.).

Forutsetningen er altså at både grensesnittet ditt og armaturene støtter RDM.
Mange moderne armaturer gjør det; eldre gjør det ikke.

## Bruk

```python
from dmx_spot_detect import detect_fixtures, OlaRDMTransport

fixtures = detect_fixtures(OlaRDMTransport(universe=1))
for f in fixtures:
    print(f.uid, f.type_label, f.model_description, f.dmx_range)
```

Kommandolinje:

```bash
python -m dmx_spot_detect --universe 1   # mot ekte maskinvare via OLA
python -m dmx_spot_detect --demo         # innebygd testdata, uten maskinvare
```

## Maskinvare

`OlaRDMTransport` bruker [Open Lighting Architecture](https://www.openlighting.org/)
(`olad` + Python-pakken `ola`), som støtter RDM over Enttec DMX USB Pro,
DMXKing, Art-Net/sACN-noder m.m. Trenger du et annet grensesnitt, implementer
`RDMTransport`-protokollen (to metoder: `discover()` og `rdm_get()`) – all
tolknings- og klassifiseringslogikk gjenbrukes uendret.

## Testing

```bash
python -m pytest tests/
```

Testene kjører mot `MockRDMTransport` og krever ingen maskinvare.
