import asyncio
import logging
import re
import shutil
from pathlib import Path
from typing import Optional

import yt_dlp

from config import DOWNLOAD_PATH, DOWNLOAD_TIMEOUT, MAX_FILE_SIZE_BYTES
from .progress import ProgressTracker
from telegram import Message

logger = logging.getLogger(__name__)

YOUTUBE_REGEX = re.compile(
    r"(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)[\w\-]+"
)

def is_valid_youtube_url(url: str) -> bool:
    """Retorna True si la URL es un enlace válido de YouTube."""
    return bool(YOUTUBE_REGEX.match(url.strip()))

def ffmpeg_available() -> bool:
    """FIX: función pública (antes _ffmpeg_available) para evitar imports de privadas desde otros módulos."""
    return shutil.which("ffmpeg") is not None

async def fetch_video_info(url: str) -> Optional[dict]:
    """Obtiene metadatos del video sin descargarlo."""
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    try:
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = await loop.run_in_executor(
                None, lambda: ydl.extract_info(url, download=False)
            )
        return info
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Error al obtener info del video: {e}")
        return None

def extract_available_formats(info: dict) -> list[dict]:
    """
    Extrae los formatos disponibles del video y los agrupa por resolución.

    Retorna una lista de dicts con:
        - id:      formato yt-dlp para usar en la descarga
        - label:   texto legible para mostrar al usuario
        - height:  altura en píxeles (para ordenar)
        - ext:     extensión del archivo
        - size:    tamaño aproximado en bytes (puede ser None)
    """
    formats    = info.get("formats", [])
    has_ffmpeg = ffmpeg_available()  # FIX: usa nombre público
    seen       = set()  # Evita duplicados de resolución+ext
    result     = []

    for f in formats:
        height = f.get("height")
        ext    = f.get("ext", "?")
        vcodec = f.get("vcodec", "none")
        acodec = f.get("acodec", "none")

        if not height or vcodec == "none":  # Descarta formatos solo-audio o sin resolución
            continue

        key = (height, ext)
        if key in seen:
            continue
        seen.add(key)

        filesize = f.get("filesize") or f.get("filesize_approx")  # Tamaño real o estimado

        if has_ffmpeg:
            # Con ffmpeg podemos combinar video+audio, ofrecemos cualquier resolución
            fmt_id = f"bestvideo[height<={height}]+bestaudio/best[height<={height}]"
        else:
            # Sin ffmpeg solo ofrecemos MP4 con audio ya incluido
            if acodec == "none":  # Formato sin audio — no sirve sin ffmpeg
                continue
            fmt_id = f"best[height<={height}][ext=mp4]/best[height<={height}]"

        result.append({
            "id":     fmt_id,
            "label":  _format_label(height, ext, filesize, has_ffmpeg),
            "height": height,
            "ext":    ext,
            "size":   filesize,
        })

    # Elimina duplicados de altura (deja el de mayor calidad por altura)
    unique: dict[int, dict] = {}
    for item in result:
        h = item["height"]
        if h not in unique or (item["size"] or 0) > (unique[h]["size"] or 0):
            unique[h] = item

    # Ordena de menor a mayor resolución y agrega MP3 al final
    sorted_formats = sorted(unique.values(), key=lambda x: x["height"])
    sorted_formats.append({  # Opción de solo audio siempre al final
        "id":     "mp3",
        "label":  "🎵 Solo Audio — MP3" if has_ffmpeg else "🎵 Solo Audio — M4A/WebM",
        "height": 0,
        "ext":    "mp3" if has_ffmpeg else "m4a",
        "size":   None,
    })

    return sorted_formats

def _format_label(height: int, ext: str, size: Optional[int], has_ffmpeg: bool) -> str:
    """Construye la etiqueta legible para un formato."""
    if height >= 1080:  # Emoji según resolución
        icon = "🎥"
    elif height >= 720:
        icon = "🎬"
    elif height >= 480:
        icon = "🖥️"
    else:
        icon = "📱"

    quality_names = {2160: "4K", 1440: "2K", 1080: "Full HD", 720: "HD", 480: "SD", 360: "360p", 240: "240p", 144: "144p"}
    quality = quality_names.get(height, f"{height}p")

    if size:  # Tamaño aproximado
        mb       = size / (1024 * 1024)
        size_str = f" ~{mb:.0f}MB" if mb >= 1 else f" ~{size//1024}KB"
    else:
        size_str = ""

    ffmpeg_note = "" if has_ffmpeg else " ⚠️"  # Aviso si no hay ffmpeg
    return f"{icon} {height}p — {quality} ({ext.upper()}){size_str}{ffmpeg_note}"

async def download_media(
    url: str,
    format_id: str,
    status_message: Message,
) -> Optional[Path]:
    """
    Descarga el video o audio desde YouTube.

    Args:
        url:            Enlace de YouTube.
        format_id:      ID del formato elegido (string de yt-dlp o 'mp3').
        status_message: Mensaje de Telegram para mostrar el progreso.

    Returns:
        Ruta al archivo descargado, 'TOO_LARGE' si supera el límite, o None si falló.
    """
    loop       = asyncio.get_event_loop()
    tracker    = ProgressTracker(status_message, loop)
    has_ffmpeg = ffmpeg_available()
    ydl_opts   = _build_ydl_opts(format_id, tracker, has_ffmpeg)

    try:
        downloaded_path = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: _run_download(url, ydl_opts)),
            timeout=DOWNLOAD_TIMEOUT,
        )

        if downloaded_path is None:
            return None

        if downloaded_path.stat().st_size > MAX_FILE_SIZE_BYTES:  # Valida límite de Telegram
            downloaded_path.unlink(missing_ok=True)
            logger.warning(f"Archivo supera el límite de tamaño: {downloaded_path}")
            return "TOO_LARGE"

        return downloaded_path

    except asyncio.TimeoutError:
        logger.error(f"Timeout al descargar: {url}")
        return None
    except Exception as e:
        logger.error(f"Error inesperado en descarga: {e}")
        return None

def _build_ydl_opts(format_id: str, tracker: ProgressTracker, has_ffmpeg: bool) -> dict:
    """Construye las opciones de yt-dlp según el formato y disponibilidad de ffmpeg."""
    output_template = str(DOWNLOAD_PATH / "%(title)s.%(ext)s")

    if format_id == "mp3":
        if has_ffmpeg:  # Con ffmpeg: extrae y convierte a MP3
            return {
                "format":         "bestaudio/best",
                "outtmpl":        output_template,
                "quiet":          True,
                "no_warnings":    True,
                "progress_hooks": [tracker.hook],
                "postprocessors": [{
                    "key":              "FFmpegExtractAudio",
                    "preferredcodec":   "mp3",
                    "preferredquality": "192",
                }],
            }
        else:  # Sin ffmpeg: descarga mejor audio nativo
            return {
                "format":         "bestaudio[ext=m4a]/bestaudio/best",
                "outtmpl":        output_template,
                "quiet":          True,
                "no_warnings":    True,
                "progress_hooks": [tracker.hook],
            }

    # Formato de video: el format_id ya viene construido desde extract_available_formats()
    opts = {
        "format":         format_id,
        "outtmpl":        output_template,
        "quiet":          True,
        "no_warnings":    True,
        "progress_hooks": [tracker.hook],
    }
    if has_ffmpeg:
        opts["merge_output_format"] = "mp4"  # Unifica en MP4 solo si ffmpeg está disponible
    return opts

def _run_download(url: str, opts: dict) -> Optional[Path]:
    """
    FIX: usa requested_downloads para obtener la ruta final real,
    que puede diferir del nombre original tras el postprocesado de ffmpeg (ej: .webm → .mp3).
    Solo cae al método de búsqueda por extensión si requested_downloads no está disponible.
    """
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)

    if info is None:
        return None

    if "entries" in info:  # Si es playlist, toma solo el primer video
        info = info["entries"][0]

    # FIX: intenta obtener la ruta real del archivo postprocesado
    requested = info.get("requested_downloads")
    if requested:
        filepath = Path(requested[0]["filepath"])
        if filepath.exists():
            return filepath

    # Fallback: busca por extensiones alternativas si la ruta directa no existe
    filepath = Path(ydl.prepare_filename(info))
    if filepath.exists():
        return filepath

    for ext in (".mp4", ".mp3", ".m4a", ".webm", ".mkv", ".opus"):
        alt = filepath.with_suffix(ext)
        if alt.exists():
            return alt

    return None
