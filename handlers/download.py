import hashlib
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import (
    MSG_DONE,
    MSG_ERROR,
    MSG_FETCHING_INFO,
    MSG_INVALID_URL,
    MSG_SELECT_FORMAT,
    MSG_TOO_LARGE,
    MSG_UPLOADING,
)
from downloader import (
    download_media,
    extract_available_formats,
    fetch_video_info,
    ffmpeg_available,
    is_valid_youtube_url,
)
from utils import cleanup_file, format_duration, format_size, safe_filename

logger = logging.getLogger(__name__)

async def handle_url_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detecta si el mensaje de texto es una URL de YouTube válida y arranca el flujo."""
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
      - Guarda la URL en bot_data usando un hash como clave
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

    formats = extract_available_formats(info)  # Formatos reales disponibles para el video
    if not formats:
        await status_msg.edit_text("❌ No se encontraron formatos disponibles para este video.")
        return

    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]  # Hash corto para usar en callback_data
    context.bot_data[url_hash] = url  # Guarda URL completa en bot_data para recuperarla después

    title    = safe_filename(info.get("title", "Sin título"))
    duration = format_duration(info.get("duration"))
    thumb    = info.get("thumbnail")

    ffmpeg_note = (
        "\n\n⚠️ *ffmpeg no instalado* — solo formatos pre-mezclados disponibles.\n"
        "Instala ffmpeg para acceder a mayor calidad."
    ) if not ffmpeg_available() else ""

    caption = (
        f"🎬 *{title}*\n"
        f"⏱️ Duración: `{duration}`\n"
        f"📊 {len(formats) - 1} calidades disponibles"  # -1 para no contar el MP3
        f"{ffmpeg_note}\n\n"
        f"{MSG_SELECT_FORMAT}"
    )

    keyboard = _build_format_keyboard(url_hash, formats)  # Pasa el hash, no la URL completa

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

def _build_format_keyboard(url_hash: str, formats: list[dict]) -> InlineKeyboardMarkup:
    """
    Construye el teclado inline con los formatos reales del video.
    Usa url_hash en callback_data para no superar el límite de 64 bytes de Telegram.
    La URL completa se recupera desde bot_data en handle_format_selection.
    """
    buttons = [
        [InlineKeyboardButton(fmt["label"], callback_data=f"dl|{i}|{url_hash}")]
        for i, fmt in enumerate(formats)
    ]
    return InlineKeyboardMarkup(buttons)

async def handle_format_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Paso 2 del flujo: recibe la selección del formato, descarga y envía el archivo.
    Recupera la URL real desde bot_data usando el hash almacenado en _process_url.
    """
    query = update.callback_query
    await query.answer()

    parts = query.data.split("|", 2)  # "dl|<indice>|<url_hash>"
    if len(parts) != 3:
        await query.message.reply_text("❌ Datos inválidos, intenta de nuevo.")
        return

    _, idx_str, url_hash = parts
    idx = int(idx_str)

    url = context.bot_data.get(url_hash)  # Recupera la URL completa desde bot_data
    if not url:
        await query.message.reply_text("❌ La sesión expiró. Envía el enlace de nuevo.")
        return

    status_msg = await query.message.reply_text("🔍 Verificando formatos...")

    info = await fetch_video_info(url)  # Vuelve a consultar para obtener el format_id real
    if info is None:
        await status_msg.edit_text("❌ No se pudo recuperar la información del video.")
        return

    formats = extract_available_formats(info)
    if idx >= len(formats):
        await status_msg.edit_text("❌ Formato no válido, intenta de nuevo.")
        return

    chosen    = formats[idx]
    format_id = chosen["id"]  # format_id real de yt-dlp (ej: "bestvideo[height<=720]+bestaudio")

    logger.info(f"Formato elegido: {chosen['label']} → {format_id}")

    await status_msg.edit_text(
        f"⏳ Iniciando descarga en *{chosen['label']}*...", parse_mode="Markdown"
    )

    # ── Descarga ───────────────────────────────────────────────────────────────
    result = await download_media(url, format_id, status_msg)

    if result == "TOO_LARGE":
        await status_msg.edit_text(MSG_TOO_LARGE)
        return

    if result is None:
        await status_msg.edit_text(
            MSG_ERROR.format(error="No se pudo completar la descarga."),
            parse_mode="Markdown",
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

        context.bot_data.pop(url_hash, None)  # Limpia la URL del bot_data tras envío exitoso

    except Exception as e:
        logger.error(f"Error al enviar archivo: {e}")
        await status_msg.edit_text(MSG_ERROR.format(error=str(e)), parse_mode="Markdown")
    finally:
        cleanup_file(result)  # Siempre elimina el archivo temporal