"""Cerebro de Jarvis: un modelo local servido por Ollama."""
import httpx

from . import config

SYSTEM = (
    "Eres Jarvis, el asistente personal de tu usuario, al estilo del Jarvis de Iron Man: "
    "educado, ingenioso y muy breve. Respondes siempre en español, en una o dos frases, "
    "porque tus respuestas se leen en voz alta. Cuando hablas de ajedrez eres un entrenador: "
    "explicas la idea de la jugada en palabras simples."
)


class Brain:
    def __init__(self) -> None:
        self.history: list[dict] = []
        self._client = httpx.AsyncClient(base_url=config.OLLAMA_URL, timeout=60)

    async def ask(self, text: str, context: str | None = None) -> str:
        user = f"{context}\n\n{text}" if context else text
        messages = [{"role": "system", "content": SYSTEM}, *self.history[-10:],
                    {"role": "user", "content": user}]
        try:
            r = await self._client.post("/api/chat", json={
                "model": config.OLLAMA_MODEL, "messages": messages,
                "stream": False, "think": False,
            })
            r.raise_for_status()
            answer = r.json()["message"]["content"].strip()
        except httpx.HTTPError as e:
            return f"No puedo pensar ahora mismo, señor: Ollama no responde ({e.__class__.__name__})."
        self.history += [{"role": "user", "content": text},
                         {"role": "assistant", "content": answer}]
        return answer

    async def close(self) -> None:
        await self._client.aclose()
