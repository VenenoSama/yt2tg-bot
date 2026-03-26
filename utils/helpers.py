import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def format_size(size_bytes: int) -> str:
    """Convierte bytes a una cadena legible (KB, MB, GB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f} MB"
    return f"{size_bytes / 1024 ** 3:.2f} GB"

def format_duration(seconds: int) -> str:
    """Convierte segundos a formato mm:ss o hh:mm:ss."""
    if seconds is None:
        return "desconocida"
    h, rem = divmod(int(seconds), 3600)
    m, s   = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def cleanup_file(path: Path) -> None:
    """Elimina un archivo si existe, sin lanzar error si no está."""
    try:
        if path and path.exists():
            path.unlink()
            logger.debug(f"Archivo eliminado: {path}")
    except Exception as e:
        logger.warning(f"No se pudo eliminar {path}: {e}")

def safe_filename(name: str, max_length: int = 60) -> str:
    """Limpia y recorta un nombre de archivo para mostrarlo en Telegram."""
    clean = name.encode("utf-8", errors="ignore").decode("utf-8")
    return clean[:max_length] + "..." if len(clean) > max_length else clean
