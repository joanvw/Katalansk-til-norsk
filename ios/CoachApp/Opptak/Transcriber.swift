import Speech

/// Transkriberer et lydopptak til tekst *på enheten* med Apples Speech-
/// rammeverk. Da forlater aldri rå lyd telefonen – kun teksten sendes til
/// backend for analyse.
struct Transcriber {
    enum TranskripsjonsFeil: LocalizedError {
        case ikkeTillatt
        case ingenGjenkjenner
        case mislyktes(String)

        var errorDescription: String? {
            switch self {
            case .ikkeTillatt: return "Talegjenkjenning er ikke tillatt."
            case .ingenGjenkjenner: return "Talegjenkjenning er utilgjengelig for norsk på denne enheten."
            case .mislyktes(let m): return "Transkripsjon mislyktes: \(m)"
            }
        }
    }

    func spørOmTillatelse() async -> Bool {
        await withCheckedContinuation { fortsett in
            SFSpeechRecognizer.requestAuthorization { status in
                fortsett.resume(returning: status == .authorized)
            }
        }
    }

    /// Transkriber filen. Foretrekker norsk gjenkjenner, faller tilbake til
    /// enhetens standard om nødvendig.
    func transkriber(_ fil: URL) async throws -> String {
        guard let gjenkjenner = SFSpeechRecognizer(locale: Locale(identifier: "nb-NO"))
            ?? SFSpeechRecognizer(), gjenkjenner.isAvailable
        else { throw TranskripsjonsFeil.ingenGjenkjenner }

        let forespørsel = SFSpeechURLRecognitionRequest(url: fil)
        forespørsel.requiresOnDeviceRecognition = true  // hold analysen lokal

        return try await withCheckedThrowingContinuation { fortsett in
            gjenkjenner.recognitionTask(with: forespørsel) { resultat, feil in
                if let feil {
                    fortsett.resume(throwing: TranskripsjonsFeil.mislyktes(feil.localizedDescription))
                } else if let resultat, resultat.isFinal {
                    fortsett.resume(returning: resultat.bestTranscription.formattedString)
                }
            }
        }
    }
}
