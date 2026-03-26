from telegram import Update
from telegram.ext import ContextTypes

_WELCOME = (
    "👋 *¡Hola! Soy tu bot descargador de YouTube.*\n\n"
    "📌 *Comandos disponibles:*\n"
    "• /download `<url>` — Descarga un video o audio\n"
    "• /status — Estado del servidor\n\n"
    "💡 Envíame un enlace de YouTube y te digo el resto."
)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Responde al comando /start con el mensaje de bienvenida."""
    await update.message.reply_text(_WELCOME, parse_mode="Markdown")