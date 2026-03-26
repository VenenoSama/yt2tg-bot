import logging
import shutil

import psutil
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler del comando /status — muestra métricas del servidor."""
    msg = await update.message.reply_text("🔄 Obteniendo estadísticas del servidor...")

    try:
        stats = _get_system_stats()  # Recolecta métricas del sistema
        text  = _format_stats(stats)
        await msg.edit_text(text, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error al obtener estado del servidor: {e}")
        await msg.edit_text(f"❌ No se pudo obtener el estado: `{e}`", parse_mode="Markdown")

def _get_system_stats() -> dict:
    """Recolecta métricas del sistema usando psutil."""
    cpu_percent = psutil.cpu_percent(interval=1)  # % de uso de CPU (espera 1s para precisión)
    ram         = psutil.virtual_memory()          # Info de RAM
    disk        = shutil.disk_usage("/")           # Espacio en disco raíz

    return {
        "cpu":      cpu_percent,
        "ram_used": ram.used / (1024 ** 3),        # Convierte bytes → GB
        "ram_total": ram.total / (1024 ** 3),
        "ram_pct":  ram.percent,
        "disk_used": disk.used / (1024 ** 3),
        "disk_total": disk.total / (1024 ** 3),
        "disk_pct":  disk.used / disk.total * 100,
    }

def _bar(percent: float, length: int = 10) -> str:
    """Genera una barra de progreso visual con bloques Unicode."""
    filled = int(percent / 100 * length)
    return "█" * filled + "░" * (length - filled)

def _format_stats(s: dict) -> str:
    """Formatea las métricas en un mensaje legible para Telegram."""
    return (
        "🖥️ *Estado del Servidor*\n\n"
        f"*CPU*\n"
        f"`[{_bar(s['cpu'])}]` {s['cpu']:.1f}%\n\n"
        f"*RAM*\n"
        f"`[{_bar(s['ram_pct'])}]` {s['ram_pct']:.1f}%\n"
        f"`{s['ram_used']:.1f} GB / {s['ram_total']:.1f} GB`\n\n"
        f"*Disco*\n"
        f"`[{_bar(s['disk_pct'])}]` {s['disk_pct']:.1f}%\n"
        f"`{s['disk_used']:.1f} GB / {s['disk_total']:.1f} GB`"
    )
