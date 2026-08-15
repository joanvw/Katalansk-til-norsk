import SwiftUI

/// Skjemaet brukeren huker av *før* opptaket: situasjon, roller, hvem du
/// møter, agenda, møtested, ønskede utfall og notater.
struct SetupView: View {
    @EnvironmentObject private var app: AppState
    var onForbered: () -> Void

    var body: some View {
        Form {
            if let valg = app.valg {
                situasjonsDel(valg)
                rolleDel(valg)
                deltakerDel(valg)
                agendaDel(valg)
                utkommeDel(valg)
                notatDel
                handlingDel
            } else {
                Section {
                    HStack { ProgressView(); Text("Henter valg …") }
                }
                backendDel
            }
        }
        .task { await app.lastValgHvisNødvendig() }
    }

    // MARK: Seksjoner

    private func situasjonsDel(_ valg: Valg) -> some View {
        Section("Situasjon") {
            Picker("Situasjon", selection: $app.oppsett.situasjon) {
                ForEach(valg.situasjoner) { Text($0.tekst).tag($0.tekst) }
            }
            Picker("Møtested", selection: $app.oppsett.møtested) {
                ForEach(valg.møtesteder) { Text($0.tekst).tag($0.tekst) }
            }
            if app.oppsett.møtested.contains("andre") {
                TextField("Utdyp møtested", text: $app.oppsett.møtestedFritekst)
            }
        }
    }

    private func rolleDel(_ valg: Valg) -> some View {
        Section("Din rolle") {
            RolleVelger(tittel: "Opplevd rolle", rolle: $app.oppsett.opplevdRolle, forslag: valg.roller)
            RolleVelger(tittel: "Faktisk rolle", rolle: $app.oppsett.faktiskRolle, forslag: valg.roller)
        }
    }

    private func deltakerDel(_ valg: Valg) -> some View {
        Section("Hvem møter du") {
            ForEach($app.oppsett.deltakere) { $deltaker in
                VStack(alignment: .leading, spacing: 8) {
                    RolleVelger(tittel: "Rolle", rolle: $deltaker.rolle, forslag: valg.roller)
                    Stepper("Antall: \(deltaker.antall)", value: $deltaker.antall, in: 1...50)
                    TextField("Opplevd relasjon (valgfritt)", text: $deltaker.opplevdRelasjon)
                        .textInputAutocapitalization(.sentences)
                }
                .padding(.vertical, 4)
            }
            .onDelete { app.oppsett.deltakere.remove(atOffsets: $0) }

            Button {
                app.oppsett.deltakere.append(Deltaker(rolle: valg.roller.first ?? ""))
            } label: {
                Label("Legg til person", systemImage: "plus.circle")
            }
        }
    }

    private func agendaDel(_ valg: Valg) -> some View {
        Section("Agenda") {
            Picker("Agenda", selection: $app.oppsett.agenda) {
                ForEach(valg.agendaer) { Text($0.tekst).tag($0.tekst) }
            }
        }
    }

    private func utkommeDel(_ valg: Valg) -> some View {
        Section("Ønsket utkomme (velg gjerne flere)") {
            ForEach(valg.ønskedeUtkommer) { alt in
                let valgt = app.oppsett.ønskedeUtkommer.contains(alt.tekst)
                Button {
                    if valgt {
                        app.oppsett.ønskedeUtkommer.removeAll { $0 == alt.tekst }
                    } else {
                        app.oppsett.ønskedeUtkommer.append(alt.tekst)
                    }
                } label: {
                    HStack {
                        Text(alt.tekst).foregroundStyle(.primary)
                        Spacer()
                        if valgt { Image(systemName: "checkmark").foregroundStyle(.tint) }
                    }
                }
            }
        }
    }

    private var notatDel: some View {
        Section("Notater (valgfritt)") {
            TextField("Din opplevde relasjon / kontekst", text: $app.oppsett.opplevdRelasjon, axis: .vertical)
            TextField("Notater før treffet", text: $app.oppsett.notater, axis: .vertical)
        }
    }

    private var handlingDel: some View {
        Section {
            Button {
                Task { if await app.forbered() { onForbered() } }
            } label: {
                Label("Forbered meg", systemImage: "sparkles").frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .disabled(app.oppsett.situasjon.isEmpty)
        } footer: {
            backendFooter
        }
    }

    private var backendDel: some View {
        Section("Backend") { backendFelt }
    }

    private var backendFooter: some View {
        backendFelt
    }

    private var backendFelt: some View {
        HStack {
            Text("Backend").foregroundStyle(.secondary)
            TextField("http://…", text: $app.baseURLtekst)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .multilineTextAlignment(.trailing)
        }
    }
}

/// Velger for en rolle: fritekstfelt med en meny av ferdigdefinerte forslag.
struct RolleVelger: View {
    let tittel: String
    @Binding var rolle: String
    let forslag: [String]

    var body: some View {
        HStack {
            TextField(tittel, text: $rolle)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
            Menu {
                ForEach(forslag, id: \.self) { valg in
                    Button(valg) { rolle = valg }
                }
            } label: {
                Image(systemName: "list.bullet")
            }
        }
    }
}
