import logging

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from config import TELEGRAM_TOKEN
from handlers import cmd_start, handle_format_selection, handle_url_message
from handlers.download import _process_url
from status import cmd_status

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    level=logging.INFO,
    datefmt="%H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)  # Silencia los logs de polling de httpx
logger = logging.getLogger(__name__)

async def cmd_download(update, context) -> None:
    """/download <url> — extrae la URL y delega al flujo principal."""
    if not context.args:
        await update.message.reply_text(
            "📎 Uso: `/download <url_de_youtube>`", parse_mode="Markdown"
        )
        return
    await _process_url(update, context, context.args[0].strip())

def main() -> None:
    """Inicializa y arranca el bot."""
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("status",   cmd_status))
    app.add_handler(CommandHandler("download", cmd_download))
    app.add_handler(CallbackQueryHandler(handle_format_selection))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url_message))

    logger.info("🤖 Bot iniciado correctamente. Esperando mensajes...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
