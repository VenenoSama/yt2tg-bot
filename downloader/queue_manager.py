"""
Sistema de cola de descargas por usuario.

Cada usuario tiene su propio semáforo que limita a MAX_CONCURRENT_PER_USER
descargas simultáneas. Si el usuario ya alcanzó el límite, recibe un mensaje
claro en lugar de que el bot lance descargas sin control.

Uso:
    async with user_queue(user_id):
        result = await download_media(...)
"""

import asyncio
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

MAX_CONCURRENT_PER_USER = 1   # Descargas simultáneas permitidas por usuario
_semaphores: dict[int, asyncio.Semaphore] = defaultdict(  # Un semáforo por user_id
    lambda: asyncio.Semaphore(MAX_CONCURRENT_PER_USER)
)

class UserBusyError(Exception):
    """Se lanza cuando el usuario ya tiene una descarga en curso y el semáforo está ocupado."""
    pass

class user_queue:
    """
    Context manager asíncrono que controla el acceso concurrente por usuario.

    Uso:
        try:
            async with user_queue(user_id):
                await download_media(...)
        except UserBusyError:
            await msg.reply_text('Ya tienes una descarga en curso...')
    """

    def __init__(self, user_id: int):
        self.user_id   = user_id
        self._sem      = _semaphores[user_id]
        self._acquired = False

    async def __aenter__(self):
        acquired = self._sem._value > 0  # Comprueba si hay slot disponible sin bloquear
        if not acquired:
            raise UserBusyError(f"Usuario {self.user_id} ya tiene una descarga en curso")
        await self._sem.acquire()
        self._acquired = True
        logger.debug(f"Slot de descarga adquirido para user_id={self.user_id}")
        return self

    async def __aexit__(self, *_):
        if self._acquired:
            self._sem.release()
            logger.debug(f"Slot de descarga liberado para user_id={self.user_id}")

def active_downloads_count(user_id: int) -> int:
    """Retorna cuántas descargas activas tiene el usuario en este momento."""
    sem = _semaphores[user_id]
    return MAX_CONCURRENT_PER_USER - sem._value