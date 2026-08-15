import SwiftUI

/// Coachens tilbakemelding *etter* treffet: styrker, forbedringsområder,
/// dialogtips per ressurs, vurdering av utfall og neste øving.
struct FeedbackView: View {
    @EnvironmentObject private var app: AppState
    var onNyØkt: () -> Void

    var body: some View {
        List {
            if let tb = app.tilbakemelding {
                punktseksjon("Styrker", tb.styrker, ikon: "plus.circle", farge: .green)
                punktseksjon("Forbedringsområder", tb.forbedringsområder, ikon: "exclamationmark.circle", farge: .orange)

                if !tb.perDeltaker.isEmpty {
                    Section("Ressursene i rommet") {
                        ForEach(tb.perDeltaker) { dt in
                            VStack(alignment: .leading, spacing: 6) {
                                Text(dt.rolle).font(.headline)
                                if !dt.observerteDrivere.isEmpty {
                                    Text("Drivere: " + dt.observerteDrivere.joined(separator: ", "))
                                        .font(.subheadline).foregroundStyle(.secondary)
                                }
                                ForEach(dt.forbedringDialog, id: \.self) { tips in
                                    Label(tips, systemImage: "arrow.right").font(.callout)
                                }
                            }
                            .padding(.vertical, 4)
                        }
                    }
                }

                if !tb.utkommeVurdering.isEmpty {
                    Section("Ønskede utfall") {
                        ForEach(tb.utkommeVurdering) { uv in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(uv.utkomme).font(.subheadline.bold())
                                Text(uv.vurdering).font(.callout).foregroundStyle(.secondary)
                            }
                        }
                    }
                }

                punktseksjon("Neste øving", tb.nesteØving, ikon: "figure.run", farge: .accentColor)
            }
        }
        .navigationTitle("Tilbakemelding")
        .safeAreaInset(edge: .bottom) {
            Button(action: onNyØkt) {
                Label("Ny økt", systemImage: "arrow.counterclockwise").frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .padding()
            .background(.bar)
        }
    }

    private func punktseksjon(_ tittel: String, _ punkter: [String], ikon: String, farge: Color) -> some View {
        Group {
            if !punkter.isEmpty {
                Section(tittel) {
                    ForEach(punkter, id: \.self) { punkt in
                        Label {
                            Text(punkt)
                        } icon: {
                            Image(systemName: ikon).foregroundStyle(farge)
                        }
                    }
                }
            }
        }
    }
}
