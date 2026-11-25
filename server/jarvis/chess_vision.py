"""Lectura de jugadas a partir de video.

No intenta reconocer cada pieza. Parte de una posición conocida (la inicial o
un FEN), endereza el tablero con sus 4 esquinas, espera a que la imagen esté
quieta (sin mano encima) y mide qué casillas cambiaron. La jugada legal cuyas
casillas mejor explican el cambio es la que se jugó.

Las esquinas salen de una calibración manual (cámara fija) o, con la cámara en
la cabeza, de 4 marcadores ArUco impresos junto a las esquinas del tablero, que
se buscan en cada cuadro.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import chess
import cv2
import numpy as np

WARP_SIZE = 640
SQ = WARP_SIZE // 8

# Marcadores ArUco (diccionario 4x4) que van junto a cada esquina del tablero.
MARKER_IDS = {0: "a1", 1: "h1", 2: "h8", 3: "a8"}
_ARUCO = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50))


def find_marker_corners(image: np.ndarray) -> np.ndarray | None:
    """Esquinas a1, h1, h8, a8 del tablero a partir de los 4 marcadores, o None si falta alguno.

    Cada marcador va por fuera de su esquina, tocándola; la esquina del tablero es la
    esquina del marcador más cercana al centro de los cuatro.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    found, ids, _ = _ARUCO.detectMarkers(gray)
    if ids is None:
        return None
    by_id = {int(i): c.reshape(4, 2) for i, c in zip(ids.flatten(), found) if int(i) in MARKER_IDS}
    if len(by_id) < 4:
        return None
    center = np.mean([c.mean(axis=0) for c in by_id.values()], axis=0)
    corners = []
    for marker_id in sorted(MARKER_IDS):
        quad = by_id[marker_id]
        corners.append(quad[np.argmin(np.linalg.norm(quad - center, axis=1))])
    return np.float32(corners)


def changed_squares(before: chess.Board, after: chess.Board) -> set[int]:
    """Casillas cuyo contenido es distinto entre dos posiciones (sirve para enroque y al paso)."""
    return {sq for sq in chess.SQUARES if before.piece_at(sq) != after.piece_at(sq)}


@dataclass
class BoardReader:
    """Sigue una partida real cuadro por cuadro."""

    board: chess.Board = field(default_factory=chess.Board)
    corners: np.ndarray | None = None  # a1, h1, h8, a8 en píxeles de la imagen
    auto_corners: bool = False  # buscar los marcadores en cada cuadro
    stable_frames_needed: int = 3
    pixel_threshold: int = 30        # diferencia LAB para contar un píxel como cambiado
    motion_threshold: float = 0.025  # fracción del tablero que cambió entre cuadros = "hay movimiento"
    change_threshold: float = 0.10   # fracción de una casilla que cambió = "cambió"

    _reference: np.ndarray | None = None
    _last: np.ndarray | None = None
    _stable_count: int = 0
    _unclear_sent: bool = False

    def calibrate(self, corners) -> None:
        self.corners = np.asarray(corners, dtype=np.float32).reshape(4, 2)
        self.auto_corners = False
        self.retrack()

    def use_markers(self) -> None:
        self.auto_corners = True
        self.corners = None
        self.retrack()

    @property
    def ready_for_frames(self) -> bool:
        return self.auto_corners or self.corners is not None

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

    def _score(self, diffs: np.ndarray, changed: set[int], squares: set[int]) -> float | None:
        if not squares or any(diffs[s] <= self.change_threshold for s in squares):
            return None
        hit = sum(diffs[s] for s in squares) / len(squares)
        miss = sum(diffs[s] for s in changed - squares)  # cambios que la jugada no explica
        return hit - miss

    def detect_moves(self, diffs: np.ndarray) -> list[chess.Move]:
        """Jugada (o par de jugadas, si no se vio la imagen entre ambas) que explica el cambio."""
        changed = {sq for sq in chess.SQUARES if diffs[sq] > self.change_threshold}
        if len(changed) < 2:
            return []
        best: list[chess.Move] = []
        best_squares: set[int] = set()
        best_score = -np.inf
        for move in self.board.legal_moves:
            after = self.board.copy(stack=False)
            after.push(move)
            squares = changed_squares(self.board, after)
            score = self._score(diffs, changed, squares)
            if score is not None and score > best_score:
                best, best_score, best_squares = [move], score, squares
        if best and not (changed - best_squares):
            return best
        # Quedaron cambios sin explicar: prueba dos jugadas seguidas.
        for move in self.board.legal_moves:
            mid = self.board.copy(stack=False)
            mid.push(move)
            for reply in mid.legal_moves:
                after = mid.copy(stack=False)
                after.push(reply)
                score = self._score(diffs, changed, changed_squares(self.board, after))
                if score is not None and score > best_score:
                    best, best_score = [move, reply], score
        return best

    def feed(self, image: np.ndarray) -> dict | None:
        """Procesa un cuadro. Devuelve un evento cuando detecta una jugada."""
        if self.auto_corners:
            corners = find_marker_corners(image)
            if corners is None:
                self._stable_count = 0  # tablero fuera de vista o tapado: no cuenta como quieto
                return None
            self.corners = corners
        frame = self.warp(image)
        if self._last is not None:
            # en baja resolución, para que el temblor de una cámara en la cabeza no cuente como movimiento
            small = (128, 128)
            motion = float(self._changed_pixels(cv2.resize(frame, small, interpolation=cv2.INTER_AREA),
                                                cv2.resize(self._last, small, interpolation=cv2.INTER_AREA)).mean())
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
        moves = self.detect_moves(diffs)
        if not moves:
            if self._unclear_sent:
                return None
            self._unclear_sent = True
            return {"type": "unclear"}
        self._unclear_sent = False
        earlier = []
        for move in moves[:-1]:
            earlier.append(self.board.san(move))
            self.board.push(move)
        move = moves[-1]
        san = self.board.san(move)
        color = "blancas" if self.board.turn == chess.WHITE else "negras"
        self.board.push(move)
        self._reference = frame
        event = {"type": "move", "san": san, "uci": move.uci(), "by": color, "fen": self.board.fen()}
        if earlier:
            event["earlier"] = earlier
        return event
