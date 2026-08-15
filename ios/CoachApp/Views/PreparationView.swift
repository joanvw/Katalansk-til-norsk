import SwiftUI

/// Coachens råd *før* treffet: sannsynlige drivere per ressurs, møtetips
/// og dialogtips rettet mot de ønskede utfallene.
struct PreparationView: View {
    @EnvironmentObject private var app: AppState
    var onStart: () -> Void

    var body: some View {
        List {
            if let f = app.forberedelse {
                if !f.sannsynligeDrivere.isEmpty {
                    Section("Drivere i rommet") {
                        ForEach(f.sannsynligeDrivere.sorted(by: { $0.key < $1.key }), id: \.key) { rolle, drivere in
                            VStack(alignment: .leading, spacing: 4) {
                                Text(rolle).font(.headline)
                                Text(drivere.joined(separator: ", "))
                                    .font(.subheadline)
                                    .foregroundStyle(.secondary)
                            }
                            .padding(.vertical, 2)
                        }
                    }
                }
                punktseksjon("Møtetips", f.møtetips, ikon: "checkmark.circle")
                punktseksjon("Dialogtips", f.dialogtips, ikon: "text.bubble")
            }
        }
        .navigationTitle("Forberedelse")
        .safeAreaInset(edge: .bottom) {
            Button(action: onStart) {
                Label("Start opptak", systemImage: "record.circle").frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .padding()
            .background(.bar)
        }
    }

    private func punktseksjon(_ tittel: String, _ punkter: [String], ikon: String) -> some View {
        Group {
            if !punkter.isEmpty {
                Section(tittel) {
                    ForEach(punkter, id: \.self) { punkt in
                        Label(punkt, systemImage: ikon)
                            .labelStyle(.titleAndIcon)
                    }
                }
            }
        }
    }
}
