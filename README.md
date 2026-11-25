# J.A.R.V.I.S.

Asistente personal estilo Jarvis que corre en tu propia PC: conversa contigo, te escucha
por voz y sigue tus partidas de ajedrez en vivo con la cámara para entrenarte.

> **Juego limpio:** usa los consejos de Stockfish para practicar, estudiar y analizar.
> Usarlos en partidas contra otras personas o en partidas con rating es hacer trampa.

## Cómo funciona

```
Cámara (Oakley Meta HSTN vía la app de iPhone, o el navegador)
        │  video en vivo (JPEG ~6 por segundo, WebSocket)
        ▼
Servidor Jarvis en tu PC (Python)
  ├─ lectura del tablero  → detecta cada jugada nueva
  ├─ Stockfish            → mejor jugada en ~0.3 s
  ├─ Ollama (IA local)    → conversación y explicaciones
  └─ bot de Telegram      → chatear con Jarvis desde cualquier lado
        │
        ▼
Respuesta hablada en el navegador (y luego en los lentes)
```

La lectura del tablero no necesita entrenar ningún modelo. Parte de una posición conocida,
endereza la imagen del tablero con las 4 esquinas que marcas una vez, espera a que tu mano
salga de la imagen y mira qué casillas cambiaron. La jugada legal que explica ese cambio es
la que se jugó (incluye capturas, enroques y al paso).

## Instalación en Windows

1. **Python 3.12**: descárgalo de <https://www.python.org/downloads/> y marca
   "Add Python to PATH" al instalar.
2. **Stockfish**: descarga la versión para Windows de <https://stockfishchess.org/download/>
   y descomprímela, por ejemplo en `C:\jarvis\stockfish\`.
3. **Ollama**: instálalo desde <https://ollama.com/download> y en una terminal ejecuta:
   ```
   ollama pull qwen3:8b
   ```
   Con tu RTX 3060 este modelo responde en uno o dos segundos.
4. **Configuración**: en la carpeta `server`, copia `.env.example` como `.env` y pon la ruta
   de `stockfish.exe` que descargaste.
5. **Arrancar**: doble clic en `server\start.bat`. La primera vez tarda unos minutos porque
   instala todo. Cuando veas `Uvicorn running on http://0.0.0.0:8000`, Jarvis está vivo.

## Probarlo

**Con la webcam de la PC:** abre <http://localhost:8000>, pulsa "Cámara", luego
"Calibrar tablero" y toca las 4 esquinas del tablero en orden a1, h1, h8, a8. Pon las piezas
en la posición inicial, aparta la mano y juega. Jarvis te dice la mejor jugada en voz alta
cuando es tu turno.

**Con el iPhone:** el navegador del iPhone solo da acceso a la cámara en páginas `https`.
La forma gratis es un túnel de Cloudflare:

1. Descarga `cloudflared` para Windows de
   <https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/>.
2. Pon una clave larga en `ACCESS_KEY` dentro de `.env` y reinicia Jarvis.
3. Ejecuta `cloudflared tunnel --url http://localhost:8000`. Te da una dirección
   `https://...trycloudflare.com`.
4. En el iPhone abre esa dirección agregando `?key=TU_CLAVE` al final.

Consejo: apoya el celular en algo fijo, mirando el tablero desde arriba o en diagonal. Si la
cámara se mueve, vuelve a calibrar.

**Telegram (opcional):** crea un bot con @BotFather, pon el token en `TELEGRAM_TOKEN`,
arranca Jarvis y escríbele `/start`. Te responderá con tu id; ponlo en
`TELEGRAM_ALLOWED_USER_ID` y reinicia. Comandos: `/tablero`, `/fen <FEN>`, `/nueva`, o
simplemente escríbele.

## Con tus lentes Oakley Meta HSTN

Como los lentes se mueven con tu cabeza, Jarvis ubica el tablero con 4 marcadores impresos.

1. **Marcadores:** imprime [`server/marcadores.png`](server/marcadores.png) al 100% (sin
   "ajustar a la página"), recórtalos por la línea y pon cada uno por fuera de su esquina,
   tocándola: 0 en a1, 1 en h1, 2 en h8, 3 en a8. Sin marcadores también se puede usar
   la página con el celular fijo y "Calibrar tablero".
2. **Modo desarrollador:** en la app Meta AI ve a Configuración, tus lentes, y activa
   "Modo desarrollador". Se apaga solo cuando los lentes se actualizan; vuelve a activarlo.
3. **Bajar la app:** en GitHub entra a la pestaña **Actions**, abre la última ejecución de
   "App de iPhone" que salió en verde y descarga **Jarvis-ipa** (es un .zip con `Jarvis.ipa`).
4. **Instalarla desde Windows con Sideloadly** (gratis):
   - Instala iTunes y iCloud en su versión de la web de Apple (no la de Microsoft Store),
     y Sideloadly de <https://sideloadly.io>.
   - Conecta el iPhone por cable, arrastra `Jarvis.ipa` a Sideloadly, pon tu Apple ID y
     pulsa Start.
   - En el iPhone: Configuración, General, VPN y gestión de dispositivos, confía en tu
     Apple ID. Desde iOS 16 también hay que activar Configuración, Privacidad y
     seguridad, Modo de desarrollador.
   - Con un Apple ID gratis la app dura 7 días. Sideloadly puede renovarla sola por Wi‑Fi
     si lo dejas abierto en la PC (opción de auto-refresh).
5. **Usarla:** abre Jarvis en el iPhone, escribe la dirección del servidor (la del túnel
   `https://…trycloudflare.com` o la IP de tu PC en casa, por ejemplo
   `192.168.1.50:8000`) y la clave, pulsa Conectar, luego "Vincular lentes con Meta AI" y
   "Ver por mis lentes". Jarvis te habla por las bocinas de los lentes.

## Pruebas

```
cd server
.venv\Scripts\python -m pip install pytest
.venv\Scripts\python -m pytest
```

Las pruebas dibujan tableros en perspectiva y verifican que se detecten aperturas, capturas,
enroque y captura al paso, y que el servidor devuelva la sugerencia de Stockfish.

## Limitaciones de esta versión

- La partida debe empezar en la posición inicial (o reiniciarse con un FEN). Si Jarvis se
  pierde, usa "Deshacer" o "Partida nueva".
- Las coronaciones se toman como dama.
- La voz usa el reconocimiento y la síntesis del navegador.

## Lo que sigue

1. **Voz local** en la PC (Whisper para entender, una voz sintética para hablar) para que
   todo funcione igual en los lentes.
2. Más habilidades para Jarvis: recordatorios, clima, música, notas.
