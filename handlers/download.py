import asyncio
import hashlib
import logging
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import (
    BOT_DATA_TTL,
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
from downloader.queue_manager import UserBusyError, user_queue
from utils import cleanup_file, format_duration, format_size, safe_filename

logger = logging.getLogger(__name__)

# Almacena la tarea asyncio activa por user_id para poder cancelarla con /cancel
_active_tasks: dict[int, asyncio.Task] = {}


# ── Gestión de caché en bot_data ──────────────────────────────────────────────

def _cache_set(bot_data: dict, url_hash: str, url: str, formats: list[dict]) -> None:
    """
    Guarda URL y formatos juntos en bot_data con timestamp de expiración.
    Así handle_format_selection no necesita volver a llamar a YouTube.
    """
    bot_data[url_hash] = {
        "url":     url,
        "formats": formats,
        "expires": time.time() + BOT_DATA_TTL,
    }

def _cache_get(bot_data: dict, url_hash: str) -> dict | None:
    """
    Recupera la entrada del caché si existe y no ha expirado.
    Elimina automáticamente las entradas vencidas.
    """
    entry = bot_data.get(url_hash)
    if entry is None:
        return None
    if time.time() > entry["expires"]:  # Entrada expirada — la limpia y avisa
        bot_data.pop(url_hash, None)
        logger.debug(f"Entrada expirada eliminada del caché: {url_hash}")
        return None
    return entry

def _cache_delete(bot_data: dict, url_hash: str) -> None:
    """Elimina una entrada del caché tras un envío exitoso."""
    bot_data.pop(url_hash, None)


# ── Handlers principales ───────────────────────────────────────────────────────

async def handle_url_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detecta si el mensaje de texto es una URL de YouTube válida y arranca el flujo."""
    text = update.message.text.strip()
    if is_valid_youtube_url(text):
        await process_url(update, context, text)
    else:
        await update.message.reply_text(
            "💬 Envíame un enlace de YouTube o usa `/download <url>`",
            parse_mode="Markdown",
        )

async def process_url(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str) -> None:
    """
    Paso 1 del flujo:
      - Valida la URL
      - Obtiene metadatos del video (desde caché de disco o YouTube)
      - Extrae los formatos disponibles
      - Guarda URL + formatos en bot_data con TTL
      - Muestra el menú de selección con formatos reales
    """
    if not is_valid_youtube_url(url):
        await update.message.reply_text(MSG_INVALID_URL)
        return

    status_msg = await update.message.reply_text(MSG_FETCHING_INFO)

    info = await fetch_video_info(url)  # Usa caché de disco si está disponible
    if info is None:
        await status_msg.edit_text("❌ No se pudo obtener información del video.")
        return

    formats = extract_available_formats(info)
    if not formats:
        await status_msg.edit_text("❌ No se encontraron formatos disponibles para este video.")
        return

    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]  # Hash corto para callback_data
    _cache_set(context.bot_data, url_hash, url, formats)  # Guarda URL + formatos con TTL

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

    keyboard = _build_format_keyboard(url_hash, formats)

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


async def handle_format_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Paso 2 del flujo: recibe la selección de formato y lanza la descarga.

    - Controla concurrencia con user_queue (1 descarga activa por usuario)
    - Registra la tarea en _active_tasks para permitir /cancel
    - Recupera formatos del caché sin llamar a YouTube
    """
    query = update.callback_query
    await query.answer()

    parts = query.data.split("|", 2)  # Formato: "dl|<indice>|<url_hash>"
    if len(parts) != 3:
        await query.message.reply_text("❌ Datos inválidos, intenta de nuevo.")
        return

    _, idx_str, url_hash = parts
    idx     = int(idx_str)
    user_id = query.from_user.id

    cached = _cache_get(context.bot_data, url_hash)
    if cached is None:
        await query.message.reply_text(
            "⏰ La sesión expiró. Envía el enlace de nuevo para continuar."
        )
        return

    formats = cached["formats"]
    url     = cached["url"]

    if idx >= len(formats):
        await query.message.reply_text("❌ Formato no válido, intenta de nuevo.")
        return

    chosen    = formats[idx]
    format_id = chosen["id"]

    # Lanza la descarga como tarea para poder cancelarla con /cancel
    task = asyncio.create_task(
        _run_download_flow(query, context, url, url_hash, format_id, chosen["label"], user_id)
    )
    _active_tasks[user_id] = task  # Registra la tarea antes de await

    try:
        await task
    except asyncio.CancelledError:
        pass  # La cancelación ya fue manejada dentro de _run_download_flow
    finally:
        _active_tasks.pop(user_id, None)  # Limpia siempre al terminar


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /cancel — cancela la descarga activa del usuario si hay una en curso.
    No afecta a otros usuarios.
    """
    user_id = update.effective_user.id
    task    = _active_tasks.get(user_id)

    if task is None or task.done():
        await update.message.reply_text("ℹ️ No tienes ninguna descarga en curso.")
        return

    task.cancel()
    await update.message.reply_text("🛑 Descarga cancelada.")
    logger.info(f"Descarga cancelada por el usuario {user_id}")


# ── Flujo interno de descarga ──────────────────────────────────────────────────

async def _run_download_flow(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    url: str,
    url_hash: str,
    format_id: str,
    label: str,
    user_id: int,
) -> None:
    """
    Ejecuta la descarga completa dentro de un user_queue.
    Maneja UserBusyError si el usuario ya tiene otra descarga activa.
    Informa al usuario si la tarea es cancelada con /cancel.
    """
    try:
        async with user_queue(user_id):
            logger.info(f"Descarga iniciada: {label} | user={user_id} | url={url}")
            status_msg = await query.message.reply_text(
                f"⏳ Iniciando descarga en *{label}*...", parse_mode="Markdown"
            )
            await _download_and_send(query, context, url, url_hash, format_id, status_msg)

    except UserBusyError:
        await query.message.reply_text(
            "⏳ Ya tienes una descarga en curso.\n"
            "Espera a que termine o usa /cancel para cancelarla."
        )
    except asyncio.CancelledError:
        try:
            await query.message.reply_text("🛑 Descarga cancelada correctamente.")
        except Exception:
            pass
        raise  # Re-lanza para que handle_format_selection lo capture


async def _download_and_send(
    query,
    context: ContextTypes.DEFAULT_TYPE,
    url: str,
    url_hash: str,
    format_id: str,
    status_msg,
) -> None:
    """Descarga el archivo y lo envía a Telegram. Limpia recursos siempre."""
    result = await download_media(url, format_id, status_msg)

    if result == "TOO_LARGE":
        await status_msg.edit_text(MSG_TOO_LARGE)
        return

    if result is None:
        await status_msg.edit_text(
            MSG_ERROR.format(error="No se pudo completar la descarga tras varios intentos."),
            parse_mode="Markdown",
        )
        return

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

        _cache_delete(context.bot_data, url_hash)  # Limpia caché tras envío exitoso

    except Exception as e:
        logger.error(f"Error al enviar archivo: {e}")
        await status_msg.edit_text(MSG_ERROR.format(error=str(e)), parse_mode="Markdown")
    finally:
        cleanup_file(result)  # Siempre elimina el archivo temporal


# ── Helpers internos ───────────────────────────────────────────────────────────

def _build_format_keyboard(url_hash: str, formats: list[dict]) -> InlineKeyboardMarkup:
    """
    Construye el teclado inline con los formatos del video.
    Usa url_hash en callback_data para no superar el límite de 64 bytes de Telegram.
    """
    buttons = [
        [InlineKeyboardButton(fmt["label"], callback_data=f"dl|{i}|{url_hash}")]
        for i, fmt in enumerate(formats)
    ]
    return InlineKeyboardMarkup(buttons)