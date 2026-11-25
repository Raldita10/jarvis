import Foundation
import UIKit

/// Conexión con el servidor de Jarvis en tu PC.
@MainActor
final class ServerLink: ObservableObject {
  @Published var connected = false

  /// Eventos del servidor (jugadas, avisos), en el hilo principal.
  var onEvent: (([String: Any]) -> Void)?

  private var baseURL: URL?
  private var key = ""
  private var socket: URLSessionWebSocketTask?
  private var sending = false
  private var lastSent = Date.distantPast
  private let minInterval: TimeInterval = 0.15  // ~6 cuadros por segundo

  func connect(base: String, key: String) {
    disconnect()
    var text = base.trimmingCharacters(in: .whitespacesAndNewlines)
    if text.hasSuffix("/") { text.removeLast() }
    if !text.contains("://") { text = "http://" + text }
    guard let url = URL(string: text) else { return }
    baseURL = url
    self.key = key
    open()
  }

  func disconnect() {
    socket?.cancel(with: .goingAway, reason: nil)
    socket = nil
    connected = false
  }

  func sendFrame(_ image: UIImage) {
    guard connected, let socket, !sending, Date().timeIntervalSince(lastSent) >= minInterval,
      let jpeg = image.jpegData(compressionQuality: 0.6)
    else { return }
    sending = true
    lastSent = Date()
    socket.send(.data(jpeg)) { [weak self] _ in
      Task { @MainActor in self?.sending = false }
    }
  }

  func send(_ message: [String: Any]) {
    guard let socket, let data = try? JSONSerialization.data(withJSONObject: message),
      let text = String(data: data, encoding: .utf8)
    else { return }
    socket.send(.string(text)) { _ in }
  }

  func chat(_ text: String) async -> String {
    guard let url = endpoint(path: "/api/chat", websocket: false) else { return "No tengo servidor configurado." }
    var request = URLRequest(url: url)
    request.httpMethod = "POST"
    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
    request.httpBody = try? JSONSerialization.data(withJSONObject: ["text": text])
    do {
      let (data, _) = try await URLSession.shared.data(for: request)
      let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
      return json?["answer"] as? String ?? "No entendí la respuesta del servidor."
    } catch {
      return "No pude hablar con el servidor."
    }
  }

  private func endpoint(path: String, websocket: Bool) -> URL? {
    guard let baseURL, var components = URLComponents(url: baseURL, resolvingAgainstBaseURL: false) else {
      return nil
    }
    if websocket {
      components.scheme = components.scheme == "https" ? "wss" : "ws"
    }
    components.path = path
    if !key.isEmpty { components.queryItems = [URLQueryItem(name: "key", value: key)] }
    return components.url
  }

  private func open() {
    guard let url = endpoint(path: "/ws/board", websocket: true) else { return }
    let socket = URLSession.shared.webSocketTask(with: url)
    self.socket = socket
    socket.resume()
    connected = true
    receive(on: socket)
  }

  private func receive(on socket: URLSessionWebSocketTask) {
    socket.receive { [weak self] result in
      Task { @MainActor in
        guard let self, self.socket === socket else { return }
        switch result {
        case .success(.string(let text)):
          if let data = text.data(using: .utf8),
            let event = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
          {
            self.onEvent?(event)
          }
          self.receive(on: socket)
        case .success:
          self.receive(on: socket)
        case .failure:
          // Se cayó la conexión: reintenta en 2 segundos.
          self.connected = false
          self.socket = nil
          try? await Task.sleep(for: .seconds(2))
          if self.baseURL != nil, self.socket == nil { self.open() }
        }
      }
    }
  }
}
