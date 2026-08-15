import Foundation
import SwiftUI

/// Delt tilstand for hele appen: valg fra backend, utkastet til oppsettet,
/// forberedelsen og tilbakemeldingen. Kjøres på hovedtråden.
@MainActor
final class AppState: ObservableObject {
    private static let backendNøkkel = "backendURL"

    /// Backend-adresse. Kan endres i skjemaet (nyttig for simulator vs. enhet),
    /// og lagres i UserDefaults mellom kjøringer.
    @Published var baseURLtekst: String {
        didSet { UserDefaults.standard.set(baseURLtekst, forKey: Self.backendNøkkel) }
    }

    @Published var valg: Valg?
    @Published var oppsett = Møteoppsett()
    @Published var forberedelse: Forberedelse?
    @Published var tilbakemelding: Tilbakemelding?

    @Published var laster = false
    @Published var feilmelding: String?

    init() {
        baseURLtekst = UserDefaults.standard.string(forKey: Self.backendNøkkel)
            ?? "http://localhost:8000"
    }

    private var api: CoachAPI? {
        URL(string: baseURLtekst).map { CoachAPI(baseURL: $0) }
    }

    /// Hent valglistene én gang, og sett fornuftige standardvalg i skjemaet.
    func lastValgHvisNødvendig() async {
        guard valg == nil, let api else { return }
        await medLasting {
            let hentet = try await api.hentValg()
            self.valg = hentet
            if self.oppsett.situasjon.isEmpty { self.oppsett.situasjon = hentet.situasjoner.first?.tekst ?? "" }
            if self.oppsett.agenda.isEmpty { self.oppsett.agenda = hentet.agendaer.first?.tekst ?? "" }
            if self.oppsett.møtested.isEmpty { self.oppsett.møtested = hentet.møtesteder.first?.tekst ?? "" }
        }
    }

    /// Be om forberedelse. Returnerer `true` ved suksess (så visningen kan gå videre).
    func forbered() async -> Bool {
        guard let api else { feilmelding = "Ugyldig backend-adresse."; return false }
        return await medLasting {
            self.forberedelse = try await api.forbered(self.oppsett)
        }
    }

    /// Be om analyse ut fra transkripsjonen fra opptaket.
    func analyser(transkripsjon: String) async -> Bool {
        guard let api else { feilmelding = "Ugyldig backend-adresse."; return false }
        return await medLasting {
            self.tilbakemelding = try await api.analyser(
                oppsett: self.oppsett,
                observasjoner: Observasjoner(transkripsjon: transkripsjon)
            )
        }
    }

    /// Nullstill for en ny økt (behold backend-adressen).
    func nyØkt() {
        oppsett = Møteoppsett()
        forberedelse = nil
        tilbakemelding = nil
        Task { await lastValgHvisNødvendig() }
    }

    // MARK: Hjelper

    @discardableResult
    private func medLasting(_ arbeid: () async throws -> Void) async -> Bool {
        laster = true
        feilmelding = nil
        defer { laster = false }
        do {
            try await arbeid()
            return true
        } catch {
            feilmelding = error.localizedDescription
            return false
        }
    }
}
