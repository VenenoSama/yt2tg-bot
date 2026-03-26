from telegram import Update
from telegram.ext import ContextTypes

from config import MSG_WELCOME  # Fuente única del mensaje — eliminado el duplicado local

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Responde al comando /start con el mensaje de bienvenida."""
    await update.message.reply_text(MSG_WELCOME, parse_mode="Markdown")