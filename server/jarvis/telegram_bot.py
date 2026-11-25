"""Bot de Telegram: texto con Jarvis y consultas de ajedrez."""
import logging

import chess
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from . import config

log = logging.getLogger(__name__)


def build(state) -> Application | None:
    if not config.TELEGRAM_TOKEN:
        log.info("Sin TELEGRAM_TOKEN: el bot de Telegram queda apagado")
        return None
    app = Application.builder().token(config.TELEGRAM_TOKEN).build()

    def allowed(update: Update) -> bool:
        return update.effective_user.id == config.TELEGRAM_ALLOWED_USER_ID

    async def deny(update: Update) -> None:
        await update.message.reply_text(
            f"No te conozco. Tu id de Telegram es {update.effective_user.id}: "
            "ponlo en TELEGRAM_ALLOWED_USER_ID del archivo .env.")

    async def start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if not allowed(update):
            return await deny(update)
        await update.message.reply_text(
            "A sus órdenes. Escríbame lo que necesite.\n"
            "/tablero  posición actual y mejor jugada\n"
            "/fen <FEN>  analizar una posición\n"
            "/nueva  empezar una partida nueva")

    async def tablero(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if not allowed(update):
            return await deny(update)
        await update.message.reply_text(await state.describe_board(state.reader.board))

    async def fen(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not allowed(update):
            return await deny(update)
        try:
            board = chess.Board(" ".join(ctx.args))
        except ValueError:
            return await update.message.reply_text("Ese FEN no es válido.")
        await update.message.reply_text(await state.describe_board(board))

    async def nueva(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if not allowed(update):
            return await deny(update)
        state.reader.reset()
        await update.message.reply_text("Tablero reiniciado a la posición inicial.")

    async def text(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        if not allowed(update):
            return await deny(update)
        await update.message.reply_text(await state.brain.ask(update.message.text))

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tablero", tablero))
    app.add_handler(CommandHandler("fen", fen))
    app.add_handler(CommandHandler("nueva", nueva))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))
    return app
