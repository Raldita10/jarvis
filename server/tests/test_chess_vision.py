"""Prueba la lectura de jugadas con tableros dibujados en perspectiva."""
import chess
import cv2
import numpy as np

from jarvis.chess_vision import BoardReader

CORNERS = np.float32([[180, 620], [820, 640], [700, 160], [260, 150]])  # a1, h1, h8, a8


def render(board: chess.Board, hand: bool = False, noise_seed: int = 0) -> np.ndarray:
    size = 640
    sq = size // 8
    img = np.zeros((size, size, 3), np.uint8)
    for s in chess.SQUARES:
        f, r = chess.square_file(s), chess.square_rank(s)
        x, y = f * sq, (7 - r) * sq
        light = (f + r) % 2 == 1
        img[y:y + sq, x:x + sq] = (170, 200, 220) if light else (60, 100, 140)
        piece = board.piece_at(s)
        if piece:
            col = (240, 240, 240) if piece.color else (30, 30, 30)
            radius = 10 + 3 * piece.piece_type
            cv2.circle(img, (x + sq // 2, y + sq // 2), radius, col, -1)
    src = np.float32([[0, size], [size, size], [size, 0], [0, 0]])
    m = cv2.getPerspectiveTransform(src, CORNERS)
    out = cv2.warpPerspective(img, m, (1000, 800), borderValue=(90, 90, 90))
    if hand:
        cv2.ellipse(out, (500, 400), (160, 90), 20, 0, 360, (120, 160, 200), -1)
    rng = np.random.default_rng(noise_seed)
    noise = rng.integers(-4, 5, out.shape, dtype=np.int16)
    return np.clip(out.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def play(moves):
    reader = BoardReader()
    reader.calibrate(CORNERS)
    truth = chess.Board()
    events = []
    seed = 0

    def show(hand=False, n=4):
        nonlocal seed
        for _ in range(n):
            seed += 1
            ev = reader.feed(render(truth, hand, seed))
            if ev:
                events.append(ev)

    show()
    for san in moves:
        show(hand=True, n=2)          # la mano tapa el tablero
        truth.push_san(san)
        show(hand=True, n=1)
        show()                        # imagen quieta con la jugada hecha
    return reader, [e for e in events if e["type"] == "move"]


def test_detects_opening_and_castling():
    moves = ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "O-O", "Nf6"]
    reader, events = play(moves)
    assert [e["san"] for e in events] == moves
    expected = chess.Board()
    for san in moves:
        expected.push_san(san)
    assert reader.board.fen() == expected.fen()


def test_detects_captures_and_en_passant():
    moves = ["e4", "d5", "exd5", "Qxd5", "Nc3", "Qa5", "d4", "c5", "d5", "e5", "dxe6"]
    _, events = play(moves)
    assert [e["san"] for e in events] == moves
