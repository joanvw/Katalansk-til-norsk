# CoachApp (iOS)

SwiftUI-skjelett for en iPhone-app som bruker coach-backenden (`coach.web`).
Appen dekker hele flyten: hent valg → fyll ut skjema → forberedelse → opptak
med transkripsjon på enheten → tilbakemelding.

> **Merk:** Dette er Swift-kildekode. Den må åpnes og bygges i **Xcode på en
> Mac** – den kan ikke kompileres i dette repoet/miljøet. Krever Xcode 15+ og
> iOS 17+ (bruker `NavigationStack`, `@AppStorage`, `AVAudioApplication`).

## Filer

```
ios/CoachApp/
  CoachApp.swift          @main – app-inngang
  Models.swift            Codable-modeller som speiler JSON-API-et
  CoachAPI.swift          async nettverksklient (/valg, /forbered, /analyser)
  AppState.swift          delt tilstand + flyt
  Info.plist              tillatelser (mikrofon, tale, kamera) + lokal http
  Opptak/
    AudioRecorder.swift   lydopptak (AVAudioRecorder)
    Transcriber.swift     transkripsjon på enheten (Speech / SFSpeechRecognizer)
  Views/
    ContentView.swift     NavigationStack som driver stegene
    SetupView.swift       avkrysningsskjemaet før opptak (+ RolleVelger)
    PreparationView.swift drivere + møte-/dialogtips
    RecordingView.swift   opptak → transkripsjon → analyse
    FeedbackView.swift    tilbakemelding etter treffet
```

## Kom i gang

1. **Start backenden** (fra repo-roten):
   ```bash
   python -m coach.web --port 8000
   # med ekte AI: sett ANTHROPIC_API_KEY først
   ```
2. **Lag et Xcode-prosjekt:** nytt iOS-app-prosjekt (SwiftUI, «CoachApp»),
   og dra inn filene under `ios/CoachApp/` (behold mappestrukturen). Slett
   den autogenererte `ContentView.swift`/`…App.swift` så de ikke kolliderer.
3. **Tillatelser:** kopiér nøklene fra `Info.plist` inn i target-ets Info
   (mikrofon, talegjenkjenning, kamera), og behold `NSAllowsLocalNetworking`
   for lokal http under utvikling.
4. **Backend-adresse:** feltet nederst i skjemaet lagrer adressen.
   - **Simulator:** `http://localhost:8000` fungerer.
   - **Fysisk iPhone:** bruk Mac-ens IP på nettverket, f.eks.
     `http://192.168.1.20:8000` (samme wifi).
5. **Kjør** på simulator eller enhet.

## Design

- **Opptak og transkripsjon skjer på enheten** (Speech-rammeverket,
  `requiresOnDeviceRecognition`). Kun *teksten* sendes til backend for analyse,
  aldri rå lyd.
- **API-nøkkelen bor på backend**, ikke i appen.
- Modellene i `Models.swift` speiler `coach.serde` én-til-én; `/valg` gjør at
  skjemaet holder seg i synk med backend uten å hardkode valgene.

## Neste steg (ikke i skjelettet)

- Video (AVCaptureSession) i tillegg til lyd.
- Lagring av opptak lokalt/iCloud og en historikk over økter.
- Anonymiserte profiler (finnes i Python-`coach.ProfilArkiv`) eksponert via
  backend, for å trene på relasjoner over tid.
- Objektive observasjoner (taletid, avbrytelser) beregnet fra opptaket.
