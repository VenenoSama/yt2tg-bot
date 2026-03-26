import logging

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from config import TELEGRAM_TOKEN
from handlers import cmd_cancel, cmd_start, handle_format_selection, handle_url_message, process_url
from downloader.metadata_cache import purge_expired
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
    await process_url(update, context, context.args[0].strip())


async def on_startup(app: Application) -> None:
    """Tareas de inicialización al arrancar el bot."""
    removed = purge_expired()  # Limpia caché de metadatos expirado del arranque anterior
    logger.info(f"Caché de metadatos limpiado al inicio: {removed} archivo(s) eliminado(s)")


def main() -> None:
    """Inicializa y arranca el bot."""
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(on_startup)  # Limpia caché expirado al iniciar
        .build()
    )

    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("status",   cmd_status))
    app.add_handler(CommandHandler("download", cmd_download))
    app.add_handler(CommandHandler("cancel",   cmd_cancel))   # Nuevo comando
    app.add_handler(CallbackQueryHandler(handle_format_selection))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url_message))

    logger.info("🤖 Bot iniciado correctamente. Esperando mensajes...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
