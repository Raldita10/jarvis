import MWDATCamera
import MWDATCore
import UIKit

/// Conexión con los lentes: vincular con Meta AI, abrir sesión y recibir el video.
@MainActor
final class Glasses: ObservableObject {
  @Published var registration: RegistrationState
  @Published var status = "Lentes sin conectar"
  @Published var preview: UIImage?
  @Published var streaming = false

  /// Recibe cada cuadro de video, en el hilo principal.
  var onFrame: ((UIImage) -> Void)?

  private let wearables = Wearables.shared
  private let selector: AutoDeviceSelector
  private var session: DeviceSession?
  private var camera: MWDATCamera.Camera?
  private var tokens: [any AnyListenerToken] = []

  init() {
    registration = wearables.registrationState
    // El selector sigue la lista de lentes desde ya, para tenerlos listos al iniciar.
    selector = AutoDeviceSelector(wearables: wearables)
    Task { [weak self] in
      guard let stream = self?.wearables.registrationStateStream() else { return }
      for await state in stream {
        self?.registration = state
      }
    }
  }

  var isRegistered: Bool { registration == .registered }

  func register() async {
    do {
      try await wearables.startRegistration()
    } catch {
      status = "No se pudo vincular: \(error.localizedDescription)"
    }
  }

  func start() async {
    guard session == nil else { return }
    do {
      let session = try wearables.createSession(deviceSelector: selector)
      self.session = session
      let states = session.stateStream()
      status = "Conectando con los lentes…"
      try session.start()
      for await state in states {
        if state == .started { break }
        if state == .stopped {
          status = "Los lentes cerraron la conexión"
          self.session = nil
          return
        }
      }

      if try await wearables.checkPermissionStatus(.camera) != .granted {
        guard try await wearables.requestPermission(.camera) == .granted else {
          status = "Sin permiso para la cámara de los lentes"
          stop()
          return
        }
      }

      let config = StreamConfiguration(videoCodec: .raw, resolution: .medium, frameRate: 15)
      guard let camera = try session.addCamera(config: config) else {
        status = "No se pudo abrir la cámara de los lentes"
        stop()
        return
      }
      self.camera = camera
      listen(to: camera.stream)
      camera.stream.start()
    } catch {
      status = "Error: \(error.localizedDescription)"
      stop()
    }
  }

  func stop() {
    camera?.stop()
    session?.stop()
    camera = nil
    session = nil
    streaming = false
    let old = tokens
    tokens = []
    Task { for token in old { await token.cancel() } }
  }

  private func listen(to stream: MWDATCamera.Stream) {
    tokens.append(stream.statePublisher.listen { [weak self] state in
      Task { @MainActor in self?.update(state) }
    })
    tokens.append(stream.errorPublisher.listen { [weak self] error in
      Task { @MainActor in self?.status = "Error de video: \(error.description)" }
    })
    tokens.append(stream.videoFramePublisher.listen { [weak self] frame in
      guard let image = frame.makeUIImage() else { return }
      Task { @MainActor in
        self?.preview = image
        self?.onFrame?(image)
      }
    })
  }

  private func update(_ state: StreamState) {
    streaming = state == .streaming
    switch state {
    case .streaming: status = "Viendo por tus lentes"
    case .waitingForDevice: status = "Esperando a los lentes… ¿los tienes puestos?"
    case .starting: status = "Abriendo la cámara…"
    case .paused: status = "Video en pausa"
    case .stopping, .stopped: status = "Video detenido"
    }
  }
}
