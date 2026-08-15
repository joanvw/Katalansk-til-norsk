# coach

En **coachende agent** som aktiverer opptak i ulike situasjoner, forbereder deg
på hvem du møter, og gir tydelig, utviklende tilbakemelding i etterkant – slik
at dere kan gå igjennom det sammen og trene på relasjonene over tid.

## Hva den gjør

1. **Oppsett før opptak** – du huker av situasjon, din opplevde/faktiske rolle,
   hvem du møter (med antall), agenda, møtested og ønsket utfall. Alle
   rollevalg er ferdigdefinerte, men fritekst er alltid lov.
2. **Forberedelse** – coachen kartlegger hvilke *drivere* de andre i rommet
   sannsynligvis har (f.eks. kontroll, tilhørighet, anerkjennelse) og gir
   konkrete møte- og dialogtips før du går inn i situasjonen.
3. **Opptak** – aktiverer lyd og/eller bilde og lagrer på mobil, lokal disk
   eller en valgt lagringsplattform.
4. **Analyse etterpå** – tydelig og utviklende: styrker, forbedringsområder,
   dialogtips per ressurs i rommet, og vurdering av om ønskede utfall ble nådd.
5. **Anonyme profiler** – husker personer du møter *uten* å lagre identiteten,
   slik at dere kan trene på håndteringen av relasjonen over tid.

## Arkitektur

Ren Python (standardbibliotek). Alt av logikk – driverkartlegging, tips og
regelbasert analyse – er forklarbart og testbart uten nett eller AI. De
maskinvare- og plattformavhengige delene ligger bak protokoller, akkurat som
`dmx_spot_detect` kobler på ekte DMX-maskinvare:

| Protokoll        | Rolle                          | Innebygd (test/demo) | Ekte bruk                         |
| ---------------- | ------------------------------ | -------------------- | --------------------------------- |
| `Opptaker`       | kilde for lyd/bilde            | `MockOpptaker`       | mobilens kamera/mikrofon          |
| `Lagringsmål`    | hvor mediet lagres             | `MinneLagring`, `LokalLagring` | skytjeneste / mobilens fillager |
| `Analysator`     | analyse av opptaket            | `RegelbasertAnalysator` | `AIAnalysator` (språkmodell)     |

En mobilapp implementerer bare disse tre protokollene – resten av pakken
gjenbrukes uendret.

## KI-analysator

`AIAnalysator` lar en språkmodell tolke transkripsjonen av opptaket og gi
tydelig, utviklende tilbakemelding. Den følger samme mønster: selve kallet til
modellen ligger bak en `KIKlient`-protokoll, slik at analysatoren kan testes
uten nett med en falsk klient. `AnthropicKlient` er den ekte implementasjonen –
den bruker Anthropics offisielle SDK og *strukturerte utdata*, så modellen
alltid svarer med gyldig JSON på `Tilbakemelding`-formen.

```python
from coach import (
    Coach, MockOpptaker, MinneLagring, ProfilArkiv,
    AIAnalysator, AnthropicKlient, RegelbasertAnalysator, Observasjoner,
)

coach = Coach(
    opptaker=MockOpptaker(),
    lagringsmål=MinneLagring(),
    arkiv=ProfilArkiv(salt="din-hemmelighet"),
    # Falbacker til regelbasert analyse hvis KI-kallet feiler:
    analysator=AIAnalysator(AnthropicKlient(), reserve=RegelbasertAnalysator()),
)

# ... oppsett, opptak som før ...
tb = coach.analyser(økt, Observasjoner(transkripsjon=transkripsjon))
```

`AnthropicKlient` krever `pip install anthropic` og at `ANTHROPIC_API_KEY` er
satt (eller en aktiv `ant auth login`-profil). SDK-et importeres først når
`AnthropicKlient` opprettes, så kjernen i pakken forblir avhengighetsfri.
Standardmodellen er `claude-opus-5`; bytt med `AnthropicKlient(modell=...)`.

## Bruk

```python
from coach import (
    Coach, MockOpptaker, MinneLagring, ProfilArkiv,
    Møteoppsett, Deltaker, Opptak, Opptaksmodus, Observasjoner,
    Situasjon, Agenda, Møtested, ØnsketUtkomme,
)

coach = Coach(
    opptaker=MockOpptaker(),                 # bytt til ekte kamera/mikk i appen
    lagringsmål=MinneLagring(),              # bytt til mobil/sky
    arkiv=ProfilArkiv(salt="din-hemmelighet"),
)

oppsett = Møteoppsett(
    situasjon=Situasjon.KUNDEREPRESENTASJON,
    opplevd_rolle="teamdeltager",
    faktisk_rolle="møteleder",
    deltakere=[Deltaker(rolle="kunde", antall=2, opplevd_relasjon="ny kontakt")],
    agenda=Agenda.RELASJONSBYGGING,
    møtested=Møtested.HOS_KUNDE,
    ønskede_utkommer=[ØnsketUtkomme.BEDRE_KUNDE],
)

økt = coach.ny_økt(oppsett, Opptak(modus=Opptaksmodus.LYD_OG_BILDE))
print(økt.forberedelse.møtetips)             # råd før treffet

coach.start_opptak(økt)                       # aktiver opptak
# ... møtet skjer ...
coach.stopp_opptak(økt)                        # lagres på valgt plattform

tb = coach.analyser(økt, Observasjoner(min_taletid_andel=0.68))
print(tb.forbedringsområder)                  # tydelige neste steg
```

Kommandolinje-demo (kjører hele løpet med simulert opptak):

```bash
python -m coach --demo
```

## Personvern

Profilarkivet lagrer **aldri** navn eller identifiserende data. Du oppgir et
privat kallenavn; arkivet lager en stabil, anonym `profil_id` ved å hashe
kallenavnet med et hemmelig salt, og viser bare et generert alias som
«Kunde A». Uten saltet kan id-en ikke reverseres til kallenavnet.

## Testing

```bash
python -m pytest tests/test_coach.py
```

Testene kjører uten maskinvare, nett eller AI.
