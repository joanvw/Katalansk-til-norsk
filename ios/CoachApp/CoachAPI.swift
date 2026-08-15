import Foundation

/// Tynn klient mot coach-backenden (`coach.web`). Alle kall er async.
struct CoachAPI {
    var baseURL: URL

    /// Feil fra API-et, med serverens melding når den finnes (`{"feil": ...}`).
    struct APIFeil: LocalizedError {
        let melding: String
        var errorDescription: String? { melding }
    }

    private struct Feilsvar: Decodable { let feil: String }
    private struct AnalyseForespørsel: Encodable {
        let oppsett: Møteoppsett
        let observasjoner: Observasjoner
    }

    // MARK: Endepunkter

    func hentValg() async throws -> Valg {
        try await get("/valg")
    }

    func forbered(_ oppsett: Møteoppsett) async throws -> Forberedelse {
        try await post("/forbered", kropp: oppsett)
    }

    func analyser(oppsett: Møteoppsett, observasjoner: Observasjoner) async throws -> Tilbakemelding {
        try await post("/analyser", kropp: AnalyseForespørsel(oppsett: oppsett, observasjoner: observasjoner))
    }

    // MARK: Hjelpere

    private func get<Svar: Decodable>(_ sti: String) async throws -> Svar {
        var req = URLRequest(url: baseURL.appendingPathComponent(sti))
        req.httpMethod = "GET"
        return try await utfør(req)
    }

    private func post<Kropp: Encodable, Svar: Decodable>(_ sti: String, kropp: Kropp) async throws -> Svar {
        var req = URLRequest(url: baseURL.appendingPathComponent(sti))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(kropp)
        return try await utfør(req)
    }

    private func utfør<Svar: Decodable>(_ req: URLRequest) async throws -> Svar {
        let (data, respons) = try await URLSession.shared.data(for: req)
        guard let http = respons as? HTTPURLResponse else {
            throw APIFeil(melding: "Uventet svar fra serveren.")
        }
        guard (200..<300).contains(http.statusCode) else {
            let melding = (try? JSONDecoder().decode(Feilsvar.self, from: data))?.feil
                ?? "HTTP \(http.statusCode)"
            throw APIFeil(melding: melding)
        }
        return try JSONDecoder().decode(Svar.self, from: data)
    }
}
