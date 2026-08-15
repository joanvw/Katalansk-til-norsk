import Foundation

// Codable-modeller som speiler JSON-API-et i `coach.web`.
// Enum-verdier sendes/mottas på sin norske tekst (f.eks. «møte på jobben»);
// valglistene tar også med en stabil `id` (enum-navnet) fra backend.

/// Ett avkrysningsvalg fra `/valg` (id = stabilt enum-navn, tekst = norsk).
struct ValgAlternativ: Codable, Identifiable, Hashable {
    let id: String
    let tekst: String
}

/// Alle ferdigdefinerte valg appen trenger for skjemaet før opptak.
struct Valg: Codable {
    let situasjoner: [ValgAlternativ]
    let agendaer: [ValgAlternativ]
    let møtesteder: [ValgAlternativ]
    let ønskedeUtkommer: [ValgAlternativ]
    let roller: [String]
    let drivere: [ValgAlternativ]
    let opptaksmodus: [ValgAlternativ]
    let lagringssteder: [ValgAlternativ]

    enum CodingKeys: String, CodingKey {
        case situasjoner, agendaer, møtesteder, roller, drivere, opptaksmodus, lagringssteder
        case ønskedeUtkommer = "ønskede_utkommer"
    }
}

/// Én person du møter. `id` er kun lokal listeidentitet (sendes ikke).
struct Deltaker: Codable, Identifiable {
    var id = UUID()
    var rolle: String
    var antall: Int = 1
    var opplevdRelasjon: String = ""

    enum CodingKeys: String, CodingKey {
        case rolle, antall
        case opplevdRelasjon = "opplevd_relasjon"
    }
}

/// Alt brukeren huker av før opptaket. Sendes til `/forbered` og `/analyser`.
struct Møteoppsett: Codable {
    var situasjon: String = ""
    var opplevdRolle: String = ""
    var faktiskRolle: String = ""
    var deltakere: [Deltaker] = []
    var agenda: String = ""
    var møtested: String = ""
    var møtestedFritekst: String = ""
    var opplevdRelasjon: String = ""
    var ønskedeUtkommer: [String] = []
    var notater: String = ""

    enum CodingKeys: String, CodingKey {
        case situasjon, agenda, deltakere, notater
        case opplevdRolle = "opplevd_rolle"
        case faktiskRolle = "faktisk_rolle"
        case møtested, møtestedFritekst = "møtested_fritekst"
        case opplevdRelasjon = "opplevd_relasjon"
        case ønskedeUtkommer = "ønskede_utkommer"
    }
}

/// Coachens råd før treffet (fra `/forbered`).
struct Forberedelse: Codable {
    let sannsynligeDrivere: [String: [String]]
    let møtetips: [String]
    let dialogtips: [String]

    enum CodingKeys: String, CodingKey {
        case møtetips, dialogtips
        case sannsynligeDrivere = "sannsynlige_drivere"
    }
}

/// Observasjoner fra opptaket. For skjelettet sender vi transkripsjonen;
/// objektive mål kan legges til senere.
struct Observasjoner: Codable {
    var transkripsjon: String = ""
}

/// Tilbakemelding på hvordan du bør møte én ressurs i rommet.
struct DeltakerTilbakemelding: Codable, Identifiable {
    var id = UUID()
    let rolle: String
    let observerteDrivere: [String]
    let forbedringDialog: [String]

    enum CodingKeys: String, CodingKey {
        case rolle
        case observerteDrivere = "observerte_drivere"
        case forbedringDialog = "forbedring_dialog"
    }
}

/// Vurdering av ett ønsket utfall.
struct UtkommeVurdering: Codable, Identifiable {
    var id = UUID()
    let utkomme: String
    let vurdering: String

    enum CodingKeys: String, CodingKey { case utkomme, vurdering }
}

/// Coachens analyse etter treffet (fra `/analyser`).
struct Tilbakemelding: Codable {
    let styrker: [String]
    let forbedringsområder: [String]
    let perDeltaker: [DeltakerTilbakemelding]
    let utkommeVurdering: [UtkommeVurdering]
    let nesteØving: [String]

    enum CodingKeys: String, CodingKey {
        case styrker, forbedringsområder
        case perDeltaker = "per_deltaker"
        case utkommeVurdering = "utkomme_vurdering"
        case nesteØving = "neste_øving"
    }
}
