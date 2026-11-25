"""Stockfish: la mejor jugada para una posición."""
import asyncio

import chess
import chess.engine

from . import config


class Engine:
    def __init__(self) -> None:
        self._engine: chess.engine.UciProtocol | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        _, self._engine = await chess.engine.popen_uci(config.STOCKFISH_PATH)

    async def stop(self) -> None:
        if self._engine:
            try:
                await self._engine.quit()
            except (chess.engine.EngineError, RuntimeError):
                pass  # Stockfish ya se cerró (p. ej. con Ctrl+C)

    async def best_move(self, board: chess.Board) -> dict | None:
        if board.is_game_over() or self._engine is None:
            return None
        async with self._lock:
            info = await self._engine.analyse(board, chess.engine.Limit(time=config.STOCKFISH_TIME))
        pv = info.get("pv") or []
        if not pv:
            return None
        score = info["score"].white()
        if score.is_mate():
            evaluation = f"mate en {abs(score.mate())}"
        else:
            evaluation = f"{score.score() / 100:+.1f}"
        return {"san": board.san(pv[0]), "uci": pv[0].uci(), "eval": evaluation}
