import AVFoundation
import SwiftUI

/// Enkelt lydopptak med AVAudioRecorder. Video kan legges til senere
/// (AVCaptureSession); skjelettet tar opp lyd og transkriberer på enheten,
/// slik at kun tekst – ikke rå lyd – trenger å gå til backend.
@MainActor
final class AudioRecorder: NSObject, ObservableObject {
    @Published var tarOpp = false
    @Published var sekunder = 0

    private var recorder: AVAudioRecorder?
    private var timer: Timer?
    private(set) var filsti: URL?

    /// Be om mikrofontillatelse (iOS 17+).
    func spørOmTillatelse() async -> Bool {
        await withCheckedContinuation { fortsett in
            AVAudioApplication.requestRecordPermission { innvilget in
                fortsett.resume(returning: innvilget)
            }
        }
    }

    func start() throws {
        let økt = AVAudioSession.sharedInstance()
        try økt.setCategory(.playAndRecord, mode: .default)
        try økt.setActive(true)

        let sti = FileManager.default.temporaryDirectory
            .appendingPathComponent("coaching-\(Int(Date().timeIntervalSince1970)).m4a")
        let innstillinger: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
            AVSampleRateKey: 44_100,
            AVNumberOfChannelsKey: 1,
            AVEncoderAudioQualityKey: AVAudioQuality.high.rawValue,
        ]
        let r = try AVAudioRecorder(url: sti, settings: innstillinger)
        r.record()
        recorder = r
        filsti = sti
        tarOpp = true
        sekunder = 0
        timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { [weak self] _ in
            Task { @MainActor in self?.sekunder += 1 }
        }
    }

    /// Stopp opptaket og returnér filen som ble skrevet.
    func stopp() -> URL? {
        recorder?.stop()
        recorder = nil
        timer?.invalidate()
        timer = nil
        tarOpp = false
        try? AVAudioSession.sharedInstance().setActive(false)
        return filsti
    }

    var varighetTekst: String {
        String(format: "%02d:%02d", sekunder / 60, sekunder % 60)
    }
}
