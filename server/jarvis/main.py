"""Servidor de Jarvis.

    python -m jarvis.main

Expone:
  /            página de prueba (cámara + voz en el navegador)
  /ws/board    WebSocket: recibe cuadros JPEG del tablero, devuelve jugadas y consejos
  /api/chat    POST {"text": "..."} -> {"answer": "..."}
"""
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import chess
import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import config, telegram_bot
from .brain import Brain
from .chess_vision import BoardReader
from .engine import Engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("jarvis")
STATIC = Path(__file__).parent / "static"


class State:
    def __init__(self) -> None:
        self.reader = BoardReader()
        self.engine = Engine()
        self.brain = Brain()
        # Color que juegas tú: Jarvis solo aconseja en tu turno. None = ambos.
        self.my_color: chess.Color | None = chess.WHITE

    async def describe_board(self, board: chess.Board) -> str:
        best = await self.engine.best_move(board)
        if not best:
            return "La partida terminó." if board.is_game_over() else "No pude analizar la posición."
        turn = "blancas" if board.turn == chess.WHITE else "negras"
        return f"Juegan {turn}. Mejor jugada: {best['san']} (evaluación {best['eval']})."


state = State()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await state.engine.start()
    bot = telegram_bot.build(state)
    if bot:
        await bot.initialize()
        await bot.start()
        await bot.updater.start_polling()
        log.info("Bot de Telegram activo")
    yield
    if bot:
        await bot.updater.stop()
        await bot.stop()
        await bot.shutdown()
    await state.engine.stop()
    await state.brain.close()


app = FastAPI(title="Jarvis", lifespan=lifespan)


def authorized(params) -> bool:
    return not config.ACCESS_KEY or params.get("key") == config.ACCESS_KEY


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


class ChatIn(BaseModel):
    text: str


@app.post("/api/chat")
async def chat(body: ChatIn, request: Request):
    if not authorized(request.query_params):
        raise HTTPException(401, "Falta la clave")
    context = f"Posición actual de la partida (FEN): {state.reader.board.fen()}"
    return {"answer": await state.brain.ask(body.text, context)}


async def coach(event: dict) -> dict:
    """Agrega a una jugada detectada la sugerencia para el siguiente turno."""
    board = state.reader.board
    if state.my_color is not None and board.turn != state.my_color:
        event["say"] = f"{event['san']}."
        return event
    best = await state.engine.best_move(board)
    if best:
        event["suggestion"] = best
        event["say"] = f"{event['by'].capitalize()} jugaron {event['san']}. Le sugiero {best['san']}."
    return event


@app.websocket("/ws/board")
async def board_ws(ws: WebSocket):
    if not authorized(ws.query_params):
        await ws.close(code=4401)
        return
    await ws.accept()
    try:
        while True:
            msg = await ws.receive()
            if msg.get("bytes"):
                if state.reader.corners is None:
                    continue
                img = cv2.imdecode(np.frombuffer(msg["bytes"], np.uint8), cv2.IMREAD_COLOR)
                if img is None:
                    continue
                event = state.reader.feed(img)
                if event is None:
                    continue
                if event["type"] == "move":
                    event = await coach(event)
                elif event["type"] == "ready":
                    event["say"] = "Tablero listo. Cuando quiera, señor."
                    if state.my_color in (None, state.reader.board.turn):
                        best = await state.engine.best_move(state.reader.board)
                        if best:
                            event["suggestion"] = best
                elif event["type"] == "unclear":
                    event["say"] = "No entendí esa jugada. Revise que las piezas estén bien puestas."
                await ws.send_json(event)
            elif msg.get("text"):
                data = json.loads(msg["text"])
                kind = data.get("type")
                if kind == "calibrate":
                    state.reader.calibrate(data["corners"])
                    await ws.send_json({"type": "calibrated"})
                elif kind == "reset":
                    state.reader.reset(data.get("fen"))
                    await ws.send_json({"type": "reset", "fen": state.reader.board.fen()})
                elif kind == "color":
                    state.my_color = {"white": chess.WHITE, "black": chess.BLACK}.get(data.get("color"))
                elif kind == "undo" and state.reader.board.move_stack:
                    state.reader.board.pop()
                    state.reader.retrack()
                    await ws.send_json({"type": "reset", "fen": state.reader.board.fen()})
            elif msg.get("type") == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        pass


def run() -> None:
    uvicorn.run(app, host=config.HOST, port=config.PORT)


if __name__ == "__main__":
    run()
