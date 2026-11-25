import SwiftUI

struct LogLine: Identifiable {
  let id = UUID()
  let text: String
}

struct ContentView: View {
  @AppStorage("serverURL") private var serverURL = ""
  @AppStorage("accessKey") private var accessKey = ""
  @AppStorage("myColor") private var myColor = "white"

  @StateObject private var glasses = Glasses()
  @StateObject private var server = ServerLink()
  @StateObject private var voice = Voice()
  @State private var log: [LogLine] = []

  var body: some View {
    NavigationStack {
      List {
        Section("Servidor (tu PC)") {
          TextField("https://….trycloudflare.com o 192.168.1.50:8000", text: $serverURL)
            .textInputAutocapitalization(.never)
            .autocorrectionDisabled()
            .keyboardType(.URL)
          SecureField("Clave (ACCESS_KEY)", text: $accessKey)
          Button(server.connected ? "Reconectar" : "Conectar") {
            server.connect(base: serverURL, key: accessKey)
          }
          Label(server.connected ? "Conectado" : "Sin conexión",
                systemImage: server.connected ? "checkmark.circle.fill" : "xmark.circle")
            .foregroundStyle(server.connected ? Color.green : Color.secondary)
        }

        Section("Lentes") {
          Text(glasses.status).foregroundStyle(.secondary)
          if !glasses.isRegistered {
            Button("Vincular lentes con Meta AI") { Task { await glasses.register() } }
          } else if glasses.streaming {
            Button("Detener video", role: .destructive) { glasses.stop() }
          } else {
            Button("Ver por mis lentes") {
              server.send(["type": "markers"])
              Task { await glasses.start() }
            }
          }
          if let image = glasses.preview {
            Image(uiImage: image)
              .resizable()
              .scaledToFit()
              .clipShape(RoundedRectangle(cornerRadius: 12))
          }
        }

        Section("Ajedrez") {
          Picker("Juego con", selection: $myColor) {
            Text("Blancas").tag("white")
            Text("Negras").tag("black")
            Text("Ambos").tag("both")
          }
          .onChange(of: myColor) { _, color in server.send(["type": "color", "color": color]) }
          HStack {
            Button("Partida nueva") { server.send(["type": "reset"]) }
            Spacer()
            Button("Deshacer") { server.send(["type": "undo"]) }
          }
          .buttonStyle(.borderless)
        }

        Section {
          Button {
            voice.toggleListening { text in ask(text) }
          } label: {
            Label(voice.listening ? "Escuchando… toca para terminar" : "Hablarle a Jarvis",
                  systemImage: voice.listening ? "waveform" : "mic.fill")
          }
        }

        Section("Jarvis") {
          ForEach(log) { line in Text(line.text).font(.callout) }
        }
      }
      .navigationTitle("J.A.R.V.I.S.")
    }
    .onAppear(perform: setUp)
  }

  private func setUp() {
    glasses.onFrame = { image in server.sendFrame(image) }
    server.onEvent = { event in handle(event) }
    if !serverURL.isEmpty {
      server.connect(base: serverURL, key: accessKey)
      server.send(["type": "color", "color": myColor])
    }
  }

  private func handle(_ event: [String: Any]) {
    let type = event["type"] as? String ?? ""
    let suggestion = (event["suggestion"] as? [String: Any])?["san"] as? String
    switch type {
    case "move":
      let by = event["by"] as? String ?? ""
      let san = event["san"] as? String ?? ""
      add("♟️ \(by): \(san)" + (suggestion.map { " → \($0)" } ?? ""))
    case "ready":
      add("✅ Tablero listo" + (suggestion.map { " → \($0)" } ?? ""))
    case "unclear":
      add("⚠️ No entendí la jugada")
    case "reset":
      add("↺ Posición reiniciada")
    case "calibrated":
      add("🔎 Buscando los marcadores del tablero")
    default:
      break
    }
    if let say = event["say"] as? String { voice.say(say) }
  }

  private func ask(_ text: String) {
    add("🗣️ \(text)")
    Task {
      let answer = await server.chat(text)
      add("🤖 \(answer)")
      voice.say(answer)
    }
  }

  private func add(_ text: String) {
    log.insert(LogLine(text: text), at: 0)
    if log.count > 50 { log.removeLast() }
  }
}
