"""
Caché de metadatos de videos en disco.

Evita llamar a la API de YouTube para videos que ya fueron consultados
recientemente. Usa archivos JSON por video en una carpeta dedicada.

Cada entrada es un archivo: cache/<hash_url>.json
con campos: url, info (dict de yt-dlp), cached_at (timestamp).

TTL configurable desde .env como METADATA_CACHE_TTL (segundos).
Por defecto: 30 minutos — tiempo razonable para que los formatos no cambien.
"""

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(os.getenv("METADATA_CACHE_PATH", "./cache"))
_TTL       = int(os.getenv("METADATA_CACHE_TTL", "1800"))  # 30 minutos por defecto
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

def _cache_path(url: str) -> Path:
    """Genera la ruta del archivo de caché para una URL dada."""
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]  # 16 chars es suficiente para evitar colisiones
    return _CACHE_DIR / f"{url_hash}.json"

def get_cached_info(url: str) -> Optional[dict]:
    """
    Retorna los metadatos del video si están en caché y no han expirado.
    Elimina el archivo si ya venció el TTL.
    """
    path = _cache_path(url)
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        age  = time.time() - data.get("cached_at", 0)

        if age > _TTL:  # Entrada expirada — la elimina del disco
            path.unlink(missing_ok=True)
            logger.debug(f"Caché expirado eliminado: {path.name} (edad: {age:.0f}s)")
            return None

        logger.debug(f"Caché hit: {path.name} (edad: {age:.0f}s)")
        return data["info"]

    except (json.JSONDecodeError, KeyError, OSError) as e:
        logger.warning(f"Error al leer caché {path.name}: {e} — se ignora")
        path.unlink(missing_ok=True)  # Archivo corrupto — lo elimina
        return None

def set_cached_info(url: str, info: dict) -> None:
    """
    Guarda los metadatos del video en disco.
    Falla silenciosamente si hay un error de escritura (el bot sigue funcionando).
    """
    path = _cache_path(url)
    try:
        payload = {
            "url":       url,
            "cached_at": time.time(),
            "info":      info,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        logger.debug(f"Metadatos guardados en caché: {path.name}")
    except OSError as e:
        logger.warning(f"No se pudo guardar caché {path.name}: {e}")

def purge_expired() -> int:
    """
    Elimina todos los archivos de caché expirados.
    Útil para llamar periódicamente (ej: al iniciar el bot).
    Retorna la cantidad de archivos eliminados.
    """
    removed = 0
    now     = time.time()
    for path in _CACHE_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if now - data.get("cached_at", 0) > _TTL:
                path.unlink()
                removed += 1
        except (json.JSONDecodeError, OSError):
            path.unlink(missing_ok=True)  # Archivo corrupto — también se elimina
            removed += 1

    if removed:
        logger.info(f"Caché de metadatos: {removed} archivo(s) expirado(s) eliminado(s)")
    return removed