import asyncio
import logging
from telegram import Message

logger = logging.getLogger(__name__)

class ProgressTracker:
    """
    Rastrea el progreso de una descarga y actualiza el mensaje en Telegram.
    Se usa como hook dentro de yt-dlp para recibir actualizaciones en tiempo real.
    """

    def __init__(self, message: Message, loop: asyncio.AbstractEventLoop):
        self.message    = message   # Mensaje de Telegram a editar
        self.loop       = loop      # Event loop para ejecutar corrutinas desde hilo síncrono
        self._last_text = ""        # Evita editar si el texto no cambió

    def hook(self, data: dict) -> None:
        """Función que yt-dlp llama en cada actualización de progreso."""
        status = data.get("status")

        if status == "downloading":
            text = self._build_downloading_text(data)
        elif status == "finished":
            text = "⚙️ Procesando el archivo..."
        else:
            return  # Ignora otros estados

        if text != self._last_text:  # Solo actualiza si el texto cambió
            self._last_text = text
            asyncio.run_coroutine_threadsafe(  # Ejecuta la corrutina desde un hilo síncrono
                self._edit_message(text), self.loop
            )

    def _build_downloading_text(self, data: dict) -> str:
        """Construye el texto de progreso con los datos de yt-dlp."""
        percent   = data.get("_percent_str",   "?%").strip()
        speed     = data.get("_speed_str",     "?/s").strip()
        total     = data.get("_total_bytes_str", "?").strip()
        eta       = data.get("_eta_str",       "?").strip()

        bar_filled = int(data.get("downloaded_bytes", 0) /  # Calcula largo de barra
                         max(data.get("total_bytes", 1), 1) * 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)

        return (
            f"⬇️ *Descargando...*\n\n"
            f"`[{bar}]` {percent}\n\n"
            f"📦 Tamaño: `{total}`\n"
            f"⚡ Velocidad: `{speed}`\n"
            f"⏱️ Tiempo restante: `{eta}`"
        )

    async def _edit_message(self, text: str) -> None:
        """Edita el mensaje de Telegram con el nuevo texto de progreso."""
        try:
            await self.message.edit_text(text, parse_mode="Markdown")
        except Exception as e:
            logger.debug(f"No se pudo actualizar el mensaje de progreso: {e}")
