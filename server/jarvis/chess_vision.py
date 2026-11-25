"""Lectura de jugadas a partir de video.

No intenta reconocer cada pieza. Parte de una posición conocida (la inicial o
un FEN), endereza el tablero con los 4 esquinas calibradas, espera a que la
imagen esté quieta (sin mano encima) y mide qué casillas cambiaron. La jugada
legal cuyas casillas mejor explican el cambio es la que se jugó.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import chess
import cv2
import numpy as np

WARP_SIZE = 640
SQ = WARP_SIZE // 8


def square_changed_squares(move: chess.Move, board: chess.Board) -> set[int]:
    """Casillas cuyo contenido cambia al jugar `move`."""
    squares = {move.from_square, move.to_square}
    if board.is_castling(move):
        rank = chess.square_rank(move.from_square)
        if chess.square_file(move.to_square) == 6:  # enroque corto
            squares |= {chess.square(7, rank), chess.square(5, rank)}
        else:
            squares |= {chess.square(0, rank), chess.square(3, rank)}
    elif board.is_en_passant(move):
        squares.add(chess.square(chess.square_file(move.to_square),
                                 chess.square_rank(move.from_square)))
    return squares


@dataclass
class BoardReader:
    """Sigue una partida real cuadro por cuadro."""

    board: chess.Board = field(default_factory=chess.Board)
    corners: np.ndarray | None = None  # a1, h1, h8, a8 en píxeles de la imagen
    stable_frames_needed: int = 3
    pixel_threshold: int = 30        # diferencia LAB para contar un píxel como cambiado
    motion_threshold: float = 0.01   # fracción del tablero que cambió entre cuadros = "hay movimiento"
    change_threshold: float = 0.08   # fracción de una casilla que cambió = "cambió"

    _reference: np.ndarray | None = None
    _last: np.ndarray | None = None
    _stable_count: int = 0
    _unclear_sent: bool = False

    def calibrate(self, corners) -> None:
        self.corners = np.asarray(corners, dtype=np.float32).reshape(4, 2)
        self.retrack()

    def retrack(self) -> None:
        """Vuelve a tomar la imagen actual como referencia (tras calibrar, reiniciar o deshacer)."""
        self._reference = None
        self._last = None
        self._stable_count = 0
        self._unclear_sent = False

    def reset(self, fen: str | None = None) -> None:
        self.board = chess.Board(fen) if fen else chess.Board()
        self.retrack()

    def warp(self, image: np.ndarray) -> np.ndarray:
        if self.corners is None:
            raise RuntimeError("Tablero sin calibrar")
        # Destino: a8 arriba a la izquierda, a1 abajo a la izquierda (vista de blancas).
        dst = np.float32([[0, WARP_SIZE], [WARP_SIZE, WARP_SIZE],
                          [WARP_SIZE, 0], [0, 0]])
        m = cv2.getPerspectiveTransform(self.corners, dst)
        warped = cv2.warpPerspective(image, m, (WARP_SIZE, WARP_SIZE))
        lab = cv2.cvtColor(warped, cv2.COLOR_BGR2LAB)
        return cv2.GaussianBlur(lab, (5, 5), 0)

    def _changed_pixels(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        diff = cv2.absdiff(a, b).astype(np.int32).sum(axis=2)
        return (diff > self.pixel_threshold).astype(np.float32)

    def square_diffs(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """Fracción de píxeles cambiados por casilla, indexada como chess.SQUARES."""
        diff = self._changed_pixels(a, b)
        out = np.zeros(64, dtype=np.float32)
        m = SQ // 6  # ignora los bordes de cada casilla
        for sq in chess.SQUARES:
            f, r = chess.square_file(sq), chess.square_rank(sq)
            y0 = (7 - r) * SQ
            x0 = f * SQ
            out[sq] = diff[y0 + m:y0 + SQ - m, x0 + m:x0 + SQ - m].mean()
        return out

    def detect_move(self, diffs: np.ndarray) -> chess.Move | None:
        changed = {sq for sq in chess.SQUARES if diffs[sq] > self.change_threshold}
        if len(changed) < 2:
            return None
        best, best_score = None, -np.inf
        for move in self.board.legal_moves:
            squares = square_changed_squares(move, self.board)
            hit = sum(diffs[s] for s in squares) / len(squares)
            # castiga casillas que cambiaron y la jugada no explica
            miss = sum(diffs[s] for s in changed - squares)
            score = hit - miss
            if all(diffs[s] > self.change_threshold for s in squares) and score > best_score:
                best, best_score = move, score
        return best

    def feed(self, image: np.ndarray) -> dict | None:
        """Procesa un cuadro. Devuelve un evento cuando detecta una jugada."""
        frame = self.warp(image)
        if self._last is not None:
            motion = float(self._changed_pixels(frame, self._last).mean())
            self._stable_count = self._stable_count + 1 if motion < self.motion_threshold else 0
        self._last = frame
        if self._stable_count < self.stable_frames_needed:
            return None
        if self._reference is None:
            self._reference = frame
            return {"type": "ready", "fen": self.board.fen()}

        diffs = self.square_diffs(self._reference, frame)
        if diffs.max() < self.change_threshold:
            return None
        move = self.detect_move(diffs)
        if move is None:
            if self._unclear_sent:
                return None
            self._unclear_sent = True
            return {"type": "unclear"}
        self._unclear_sent = False
        san = self.board.san(move)
        color = "blancas" if self.board.turn == chess.WHITE else "negras"
        self.board.push(move)
        self._reference = frame
        return {"type": "move", "san": san, "uci": move.uci(), "by": color,
                "fen": self.board.fen()}
