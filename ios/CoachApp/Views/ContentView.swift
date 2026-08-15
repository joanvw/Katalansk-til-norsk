import SwiftUI

/// Stegene i én coaching-økt.
enum Steg: Hashable {
    case forberedelse
    case opptak
    case tilbakemelding
}

/// Rot-visningen: en NavigationStack som driver flyten
/// oppsett → forberedelse → opptak → tilbakemelding.
struct ContentView: View {
    @EnvironmentObject private var app: AppState
    @State private var sti: [Steg] = []

    var body: some View {
        NavigationStack(path: $sti) {
            SetupView(onForbered: { sti.append(.forberedelse) })
                .navigationTitle("Ny økt")
                .navigationDestination(for: Steg.self) { steg in
                    switch steg {
                    case .forberedelse:
                        PreparationView(onStart: { sti.append(.opptak) })
                    case .opptak:
                        RecordingView(onFerdig: { sti.append(.tilbakemelding) })
                    case .tilbakemelding:
                        FeedbackView(onNyØkt: {
                            app.nyØkt()
                            sti.removeAll()
                        })
                    }
                }
        }
        .overlay { if app.laster { LasteOverlegg() } }
        .alert("Noe gikk galt", isPresented: Binding(
            get: { app.feilmelding != nil },
            set: { if !$0 { app.feilmelding = nil } }
        )) {
            Button("OK", role: .cancel) { app.feilmelding = nil }
        } message: {
            Text(app.feilmelding ?? "")
        }
    }
}

/// Enkelt lasteoverlegg vist mens et API-kall pågår.
struct LasteOverlegg: View {
    var body: some View {
        ZStack {
            Color.black.opacity(0.15).ignoresSafeArea()
            ProgressView().controlSize(.large).padding(24)
                .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16))
        }
    }
}
