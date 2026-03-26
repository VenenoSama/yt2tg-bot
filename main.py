import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import (
    MSG_DONE,
    MSG_ERROR,
    MSG_FETCHING_INFO,
    MSG_INVALID_URL,
    MSG_SELECT_FORMAT,
    MSG_TOO_LARGE,
    MSG_UPLOADING,
    MSG_WELCOME,
    TELEGRAM_TOKEN,
)
from downloader import download_media, extract_available_formats, fetch_video_info, is_valid_youtube_url
from status import cmd_status
from utils import cleanup_file, format_duration, format_size, safe_filename

# ── Configuración de logs ──────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    level=logging.INFO,
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Handlers de comandos ───────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Responde al comando /start con el mensaje de bienvenida."""
    await update.message.reply_text(MSG_WELCOME, parse_mode="Markdown")

async def cmd_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/download <url> — inicia el flujo de descarga."""
    if not context.args:
        await update.message.reply_text(
            "📎 Uso: `/download <url_de_youtube>`", parse_mode="Markdown"
        )
        return
    await _process_url(update, context, context.args[0].strip())

async def handle_url_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detecta si el usuario envía un enlace de YouTube directamente en el chat."""
    text = update.message.text.strip()
    if is_valid_youtube_url(text):
        await _process_url(update, context, text)
    else:
        await update.message.reply_text(
            "💬 Envíame un enlace de YouTube o usa `/download <url>`",
            parse_mode="Markdown",
        )

async def _process_url(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str) -> None:
    """
    Paso 1 del flujo:
      - Valida la URL
      - Obtiene info real del video desde YouTube
      - Extrae los formatos disponibles
      - Muestra el menú de selección con formatos reales
    """
    if not is_valid_youtube_url(url):
        await update.message.reply_text(MSG_INVALID_URL)
        return

    status_msg = await update.message.reply_text(MSG_FETCHING_INFO)

    info = await fetch_video_info(url)  # Obtiene metadatos sin descargar
    if info is None:
        await status_msg.edit_text("❌ No se pudo obtener información del video.")
        return

    # Extrae los formatos reales disponibles para ese video específico
    formats = extract_available_formats(info)

    if not formats:
        await status_msg.edit_text("❌ No se encontraron formatos disponibles para este video.")
        return

    title    = safe_filename(info.get("title", "Sin título"))
    duration = format_duration(info.get("duration"))
    thumb    = info.get("thumbnail")

    # Informa si ffmpeg no está disponible
    from downloader.downloader import _ffmpeg_available
    ffmpeg_note = (
        "\n\n⚠️ *ffmpeg no instalado* — solo formatos pre-mezclados disponibles.\n"
        "Instala ffmpeg para acceder a mayor calidad."
    ) if not _ffmpeg_available() else ""

    caption = (
        f"🎬 *{title}*\n"
        f"⏱️ Duración: `{duration}`\n"
        f"📊 {len(formats) - 1} calidades disponibles"  # -1 para no contar el MP3
        f"{ffmpeg_note}\n\n"
        f"{MSG_SELECT_FORMAT}"
    )

    keyboard = _build_format_keyboard(url, formats)  # Teclado con formatos reales

    await status_msg.delete()

    if thumb:
        await update.message.reply_photo(
            photo=thumb, caption=caption,
            parse_mode="Markdown", reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            caption, parse_mode="Markdown", reply_markup=keyboard
        )

def _build_format_keyboard(url: str, formats: list[dict]) -> InlineKeyboardMarkup:
    """
    Construye el teclado inline con los formatos reales del video.
    Cada botón codifica el índice del formato en lugar del format_id completo
    (los format_id de yt-dlp pueden ser muy largos para callback_data).
    El formato se guarda en el contexto usando el índice como clave.
    """
    buttons = []
    for i, fmt in enumerate(formats):
        # callback_data: "dl|<indice>|<url>"
        # Usamos índice para no superar el límite de 64 bytes de Telegram
        callback = f"dl|{i}|{url}"
        if len(callback) > 64:  # Si la URL es muy larga, la recortamos con hash
            import hashlib
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            callback = f"dl|{i}|{url_hash}"
            # Guardamos la URL completa en bot_data para recuperarla después
        buttons.append([InlineKeyboardButton(fmt["label"], callback_data=f"dl|{i}|{url}")])

    return InlineKeyboardMarkup(buttons)

async def handle_format_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Paso 2 del flujo: recibe la selección del formato y ejecuta la descarga.
    Para recuperar el format_id real, vuelve a consultar la info del video.
    """
    query = update.callback_query
    await query.answer()

    parts = query.data.split("|", 2)  # "dl|<indice>|<url>"
    if len(parts) != 3:
        await query.message.reply_text("❌ Datos inválidos, intenta de nuevo.")
        return

    _, idx_str, url = parts
    idx = int(idx_str)

    status_msg = await query.message.reply_text("🔍 Verificando formatos...")

    # Recupera los formatos del video para obtener el format_id real según el índice
    info = await fetch_video_info(url)
    if info is None:
        await status_msg.edit_text("❌ No se pudo recuperar la información del video.")
        return

    formats   = extract_available_formats(info)
    if idx >= len(formats):
        await status_msg.edit_text("❌ Formato no válido, intenta de nuevo.")
        return

    chosen    = formats[idx]
    format_id = chosen["id"]    # format_id real de yt-dlp (ej: "bestvideo[height<=720]+bestaudio")

    logger.info(f"Formato elegido: {chosen['label']} → {format_id}")

    await status_msg.edit_text(f"⏳ Iniciando descarga en *{chosen['label']}*...", parse_mode="Markdown")

    # ── Descarga ───────────────────────────────────────────────────────────────
    result = await download_media(url, format_id, status_msg)

    if result == "TOO_LARGE":
        await status_msg.edit_text(MSG_TOO_LARGE)
        return

    if result is None:
        await status_msg.edit_text(
            MSG_ERROR.format(error="No se pudo completar la descarga."),
            parse_mode="Markdown"
        )
        return

    # ── Subida a Telegram ──────────────────────────────────────────────────────
    await status_msg.edit_text(MSG_UPLOADING)

    try:
        file_size = format_size(result.stat().st_size)
        caption   = f"✅ {safe_filename(result.stem)}\n📦 `{file_size}`"

        if format_id == "mp3":
            with open(result, "rb") as f:
                await query.message.reply_audio(audio=f, caption=caption, parse_mode="Markdown")
        else:
            with open(result, "rb") as f:
                await query.message.reply_video(video=f, caption=caption, parse_mode="Markdown")

        await status_msg.edit_text(MSG_DONE)
        logger.info(f"Archivo enviado: {result.name}")

    except Exception as e:
        logger.error(f"Error al enviar archivo: {e}")
        await status_msg.edit_text(MSG_ERROR.format(error=str(e)), parse_mode="Markdown")
    finally:
        cleanup_file(result)  # Siempre elimina el archivo temporal

# ── Punto de entrada ───────────────────────────────────────────────────────────

def main() -> None:
    """Inicializa y arranca el bot."""
    if not TELEGRAM_TOKEN:
        raise ValueError("❌ TELEGRAM_TOKEN no está configurado en el archivo .env")

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
