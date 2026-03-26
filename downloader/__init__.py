# Expone las funciones principales del módulo de descarga
# FIX: exporta ffmpeg_available para evitar imports internos desde main.py
from .downloader import download_media, extract_available_formats, fetch_video_info, is_valid_youtube_url, ffmpeg_available

__all__ = ["download_media", "extract_available_formats", "fetch_video_info", "is_valid_youtube_url", "ffmpeg_available"]