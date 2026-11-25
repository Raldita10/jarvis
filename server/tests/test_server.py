"""Prueba de punta a punta: cuadros por WebSocket -> jugada + sugerencia de Stockfish."""
import shutil

import chess
import cv2
import pytest
from fastapi.testclient import TestClient

from jarvis import config
from tests.test_chess_vision import CORNERS, render

pytestmark = pytest.mark.skipif(
    not (shutil.which(config.STOCKFISH_PATH) or shutil.which("/usr/games/stockfish")),
    reason="Stockfish no instalado")


def test_board_websocket(monkeypatch):
    if not shutil.which(config.STOCKFISH_PATH):
        monkeypatch.setattr(config, "STOCKFISH_PATH", "/usr/games/stockfish")
    monkeypatch.setattr(config, "TELEGRAM_TOKEN", "")
    from jarvis.main import app, state
    state.reader.reset()

    def jpeg(board, hand=False, seed=0):
        return cv2.imencode(".jpg", render(board, hand, seed))[1].tobytes()

    with TestClient(app) as client, client.websocket_connect("/ws/board") as ws:
        ws.send_json({"type": "color", "color": "black"})
        ws.send_json({"type": "calibrate", "corners": CORNERS.tolist()})
        assert ws.receive_json()["type"] == "calibrated"
        board = chess.Board()
        for i in range(4):
            ws.send_bytes(jpeg(board, seed=i))
        assert ws.receive_json()["type"] == "ready"
        ws.send_bytes(jpeg(board, hand=True, seed=10))
        board.push_san("e4")
        for i in range(4):
            ws.send_bytes(jpeg(board, seed=20 + i))
        ev = ws.receive_json()
        assert ev["type"] == "move" and ev["san"] == "e4"
        assert chess.Move.from_uci(ev["suggestion"]["uci"]) in board.legal_moves


def test_access_key_required(monkeypatch):
    monkeypatch.setattr(config, "ACCESS_KEY", "secreta")
    monkeypatch.setattr(config, "TELEGRAM_TOKEN", "")
    if not shutil.which(config.STOCKFISH_PATH):
        monkeypatch.setattr(config, "STOCKFISH_PATH", "/usr/games/stockfish")
    from jarvis.main import app
    with TestClient(app) as client:
        assert client.post("/api/chat", json={"text": "hola"}).status_code == 401
