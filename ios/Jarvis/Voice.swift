import AVFoundation
import Speech

/// La voz de Jarvis (sale por las bocinas de los lentes cuando están conectados) y tu micrófono.
@MainActor
final class Voice: ObservableObject {
  @Published var listening = false

  private let synthesizer = AVSpeechSynthesizer()
  private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "es-MX"))
  private let engine = AVAudioEngine()
  private var request: SFSpeechAudioBufferRecognitionRequest?
  private var task: SFSpeechRecognitionTask?
  private var heard = ""
  private var onText: ((String) -> Void)?

  init() {
    let audio = AVAudioSession.sharedInstance()
    // Bluetooth: el audio va y viene de los lentes.
    try? audio.setCategory(.playAndRecord, mode: .default,
                           options: [.allowBluetooth, .allowBluetoothA2DP, .defaultToSpeaker])
    try? audio.setActive(true)
  }

  func say(_ text: String) {
    let utterance = AVSpeechUtterance(string: text)
    utterance.voice = AVSpeechSynthesisVoice(language: "es-MX")
    synthesizer.stopSpeaking(at: .immediate)
    synthesizer.speak(utterance)
  }

  /// Primer toque empieza a escuchar; el segundo termina y entrega lo que oyó.
  func toggleListening(onText: @escaping (String) -> Void) {
    if listening {
      finish()
      return
    }
    self.onText = onText
    SFSpeechRecognizer.requestAuthorization { status in
      Task { @MainActor in
        guard status == .authorized else { return }
        AVAudioApplication.requestRecordPermission { granted in
          Task { @MainActor in if granted { self.begin() } }
        }
      }
    }
  }

  private func begin() {
    guard let recognizer, recognizer.isAvailable else { return }
    synthesizer.stopSpeaking(at: .immediate)
    heard = ""
    let request = SFSpeechAudioBufferRecognitionRequest()
    request.shouldReportPartialResults = true
    self.request = request
    let input = engine.inputNode
    input.removeTap(onBus: 0)
    input.installTap(onBus: 0, bufferSize: 1024, format: input.outputFormat(forBus: 0)) { buffer, _ in
      request.append(buffer)
    }
    engine.prepare()
    do {
      try engine.start()
    } catch {
      return
    }
    listening = true
    task = recognizer.recognitionTask(with: request) { [weak self] result, error in
      let text = result?.bestTranscription.formattedString
      let done = error != nil || (result?.isFinal ?? false)
      Task { @MainActor in
        guard let self else { return }
        if let text { self.heard = text }
        if done { self.deliver() }
      }
    }
  }

  private func finish() {
    engine.stop()
    engine.inputNode.removeTap(onBus: 0)
    request?.endAudio()
    listening = false
  }

  private func deliver() {
    if listening { finish() }
    task = nil
    request = nil
    let text = heard.trimmingCharacters(in: .whitespaces)
    heard = ""
    if !text.isEmpty { onText?(text) }
    onText = nil
  }
}
