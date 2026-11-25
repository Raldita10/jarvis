import MWDATCore
import SwiftUI

@main
struct JarvisApp: App {
  init() {
    do {
      try Wearables.configure()
    } catch {
      NSLog("[Jarvis] No se pudo iniciar el kit de Meta: \(error)")
    }
  }

  var body: some Scene {
    WindowGroup {
      ContentView()
        .onOpenURL { url in
          // La app Meta AI nos devuelve aquí tras vincular los lentes o dar permisos.
          guard
            let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
            components.queryItems?.contains(where: { $0.name == "metaWearablesAction" }) == true
          else { return }
          Task { _ = try? await Wearables.shared.handleUrl(url) }
        }
    }
  }
}
