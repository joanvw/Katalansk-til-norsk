import SwiftUI

/// Opptaksskjermen: ta opp lyd, transkriber på enheten, og be om analyse.
struct RecordingView: View {
    @EnvironmentObject private var app: AppState
    @StateObject private var opptaker = AudioRecorder()
    var onFerdig: () -> Void

    @State private var status: Status = .klar
    @State private var lokalFeil: String?

    enum Status: Equatable {
        case klar, tarOpp, transkriberer, analyserer
    }

    var body: some View {
        VStack(spacing: 28) {
            Spacer()

            Text(statusTekst)
                .font(.title3)
                .foregroundStyle(.secondary)

            if opptaker.tarOpp {
                Text(opptaker.varighetTekst)
                    .font(.system(size: 56, weight: .semibold, design: .rounded))
                    .monospacedDigit()
            }

            if status == .transkriberer || status == .analyserer {
                ProgressView().controlSize(.large)
            } else {
                opptaksknapp
            }

            if let lokalFeil {
                Text(lokalFeil).foregroundStyle(.red).font(.footnote).padding(.horizontal)
            }

            Spacer()
        }
        .padding()
        .navigationTitle("Opptak")
        .interactiveDismissDisabled(opptaker.tarOpp)
    }

    private var opptaksknapp: some View {
        Button {
            opptaker.tarOpp ? stoppOgAnalyser() : start()
        } label: {
            Image(systemName: opptaker.tarOpp ? "stop.circle.fill" : "record.circle")
                .resizable()
                .frame(width: 96, height: 96)
                .foregroundStyle(opptaker.tarOpp ? .red : .accentColor)
        }
        .disabled(status == .transkriberer || status == .analyserer)
    }

    private var statusTekst: String {
        switch status {
        case .klar: return "Trykk for å starte opptak"
        case .tarOpp: return "Tar opp …"
        case .transkriberer: return "Transkriberer på enheten …"
        case .analyserer: return "Coachen analyserer …"
        }
    }

    // MARK: Handlinger

    private func start() {
        lokalFeil = nil
        Task {
            let mikk = await opptaker.spørOmTillatelse()
            let tale = await Transcriber().spørOmTillatelse()
            guard mikk else { lokalFeil = "Appen trenger mikrofontilgang."; return }
            guard tale else { lokalFeil = "Appen trenger tilgang til talegjenkjenning."; return }
            do {
                try opptaker.start()
                status = .tarOpp
            } catch {
                lokalFeil = error.localizedDescription
            }
        }
    }

    private func stoppOgAnalyser() {
        guard let fil = opptaker.stopp() else { return }
        Task {
            do {
                status = .transkriberer
                let transkripsjon = try await Transcriber().transkriber(fil)
                status = .analyserer
                let ok = await app.analyser(transkripsjon: transkripsjon)
                status = .klar
                if ok { onFerdig() }
            } catch {
                status = .klar
                lokalFeil = error.localizedDescription
            }
        }
    }
}
