import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # Carga las variables desde el archivo .env

# ── Token del bot ──────────────────────────────────────────────────────────────
TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")

# FIX: valida el token al importar config, no en main() — falla rápido y claro
if not TELEGRAM_TOKEN:
    sys.exit("❌ TELEGRAM_TOKEN no está configurado en el archivo .env")

# ── ID del administrador (para comandos restringidos) ──────────────────────────
ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))

# ── Ruta de descargas ──────────────────────────────────────────────────────────
DOWNLOAD_PATH: Path = Path(os.getenv("DOWNLOAD_PATH", "./downloads"))
DOWNLOAD_PATH.mkdir(parents=True, exist_ok=True)  # Crea la carpeta si no existe

# ── Límite de tamaño de archivo para Telegram (en bytes) ──────────────────────
MAX_FILE_SIZE_MB: int    = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024

# ── Tiempo máximo de espera para descargas ─────────────────────────────────────
DOWNLOAD_TIMEOUT: int = int(os.getenv("DOWNLOAD_TIMEOUT", "300"))

# ── Formatos de video disponibles para el usuario ─────────────────────────────
VIDEO_FORMATS: list[dict] = [
    {"id": "360",  "label": "📱 360p  — Liviano"},
    {"id": "480",  "label": "🖥️ 480p  — Estándar"},
    {"id": "720",  "label": "🎬 720p  — HD"},
    {"id": "1080", "label": "🎥 1080p — Full HD"},
]

# ── Formato de audio disponible ────────────────────────────────────────────────
AUDIO_FORMAT: dict = {"id": "mp3", "label": "🎵 Solo Audio — MP3"}

# ── Mensajes del bot (centralizados para fácil edición) ───────────────────────
MSG_WELCOME = (
    "👋 *¡Hola! Soy tu bot descargador de YouTube.*\n\n"
    "📌 *Comandos disponibles:*\n"
    "• /download `<url>` — Descarga un video o audio\n"
    "• /status — Estado del servidor\n\n"
    "💡 Envíame un enlace de YouTube y te digo el resto."
)

MSG_INVALID_URL   = "❌ El enlace no parece válido. Asegúrate de que sea una URL de YouTube."
MSG_FETCHING_INFO = "🔍 Obteniendo información del video..."
MSG_SELECT_FORMAT = "🎞️ *Selecciona el formato de descarga:*"
MSG_DOWNLOADING   = "⬇️ Descargando... `{percent}%` a `{speed}`"
MSG_PROCESSING    = "⚙️ Procesando el archivo..."
MSG_UPLOADING     = "📤 Subiendo a Telegram..."
MSG_DONE          = "✅ ¡Listo! Aquí tienes tu archivo."
MSG_TOO_LARGE     = f"⚠️ El archivo supera el límite de {MAX_FILE_SIZE_MB}MB permitido por Telegram."
MSG_ERROR         = "❌ Ocurrió un error: `{error}`"
