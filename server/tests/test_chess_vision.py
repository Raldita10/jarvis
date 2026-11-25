"""Prueba la lectura de jugadas con tableros dibujados en perspectiva."""
import chess
import cv2
import numpy as np

from jarvis.chess_vision import BoardReader

CORNERS = np.float32([[180, 620], [820, 640], [700, 160], [260, 150]])  # a1, h1, h8, a8


def render_flat(board: chess.Board) -> np.ndarray:
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
    return img


def render(board: chess.Board, hand: bool = False, noise_seed: int = 0) -> np.ndarray:
    size = 640
    img = render_flat(board)
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


def render_with_markers(board: chess.Board, hand: bool = False, seed: int = 0) -> np.ndarray:
    """Tablero con marcadores ArUco en las esquinas, visto desde una cabeza que se mueve un poco."""
    size, pad, mk = 640, 70, 60
    canvas = np.full((size + 2 * pad, size + 2 * pad, 3), 235, np.uint8)
    flat = render_flat(board)
    canvas[pad:pad + size, pad:pad + size] = flat
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    # a1 abajo izquierda, h1 abajo derecha, h8 arriba derecha, a8 arriba izquierda
    spots = {0: (pad - mk, pad + size), 1: (pad + size, pad + size),
             2: (pad + size, pad - mk), 3: (pad - mk, pad - mk)}
    for marker_id, (x, y) in spots.items():
        tag = cv2.aruco.generateImageMarker(dictionary, marker_id, mk)
        canvas[y:y + mk, x:x + mk] = cv2.cvtColor(tag, cv2.COLOR_GRAY2BGR)
    rng = np.random.default_rng(seed)
    total = size + 2 * pad
    src = np.float32([[0, total], [total, total], [total, 0], [0, 0]])
    base = np.float32([[150, 700], [860, 720], [760, 90], [230, 80]])
    dst = base + rng.uniform(-6, 6, base.shape).astype(np.float32)  # la cabeza se mueve
    m = cv2.getPerspectiveTransform(src, dst)
    out = cv2.warpPerspective(canvas, m, (1000, 800), borderValue=(90, 90, 90))
    if hand:
        cv2.ellipse(out, (500, 400), (160, 90), 20, 0, 360, (120, 160, 200), -1)
    noise = rng.integers(-4, 5, out.shape, dtype=np.int16)
    return np.clip(out.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def test_markers_follow_a_moving_camera():
    reader = BoardReader()
    reader.use_markers()
    truth = chess.Board()
    moves = ["d4", "Nf6", "c4", "e6", "Nc3", "Bb4"]
    events, seed = [], 0

    def show(hand=False, n=4):
        nonlocal seed
        for _ in range(n):
            seed += 1
            ev = reader.feed(render_with_markers(truth, hand, seed))
            if ev:
                events.append(ev)

    show()
    for san in moves:
        show(hand=True, n=2)
        truth.push_san(san)
        show()
    assert [e["san"] for e in events if e["type"] == "move"] == moves


def test_two_moves_seen_at_once():
    reader = BoardReader()
    reader.calibrate(CORNERS)
    truth = chess.Board()
    for i in range(4):
        reader.feed(render(truth, noise_seed=i))
    reader.feed(render(truth, hand=True, noise_seed=10))
    truth.push_san("e4")
    truth.push_san("c5")  # la segunda jugada llega antes de que la imagen se quede quieta
    events = [reader.feed(render(truth, noise_seed=20 + i)) for i in range(5)]
    moves = [e for e in events if e and e["type"] == "move"]
    assert len(moves) == 1
    assert moves[0]["earlier"] == ["e4"] and moves[0]["san"] == "c5"
