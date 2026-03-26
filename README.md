# yt2tg-bot
# 🎬 YouTube Downloader Bot

Bot de Telegram para descargar videos y audio de YouTube, con selección de calidad, barra de progreso en tiempo real y métricas del servidor.

---

## ✨ Características

- 📥 Descarga videos de YouTube en múltiples resoluciones (hasta 4K si están disponibles)
- 🎵 Extracción de audio en MP3 (o M4A si no hay ffmpeg)
- 📊 Detección automática de formatos disponibles para cada video
- ⚡ Barra de progreso en tiempo real dentro del chat
- 🖼️ Vista previa con miniatura, título y duración del video
- 🖥️ Comando `/status` con métricas de CPU, RAM y disco del servidor
- ⚠️ Funciona con y sin `ffmpeg` instalado

---

## 📁 Estructura del proyecto

```
youtube-bot/
├── main.py          # Punto de entrada y handlers del bot
├── downloader.py    # Lógica de descarga con yt-dlp
├── progress.py      # Tracker de progreso en tiempo real
├── config.py        # Configuración y mensajes centralizados
├── status.py        # Handler del comando /status
├── helpers.py       # Utilidades: formato de tamaño, duración, limpieza
├── requirements.txt # Dependencias del proyecto
└── .env             # Variables de entorno (no subir al repo)
```

---

## ⚙️ Requisitos

- Python 3.10 o superior
- `ffmpeg` instalado en el sistema *(opcional, pero recomendado para mayor calidad)*

---

## 🚀 Instalación

**1. Clona el repositorio**
```bash
git clone https://github.com/tu-usuario/youtube-bot.git
cd youtube-bot
```

**2. Crea un entorno virtual e instala dependencias**
```bash
python -m venv venv
source venv/bin/activate       # Linux/macOS
venv\Scripts\activate          # Windows

pip install -r requirements.txt
```

**3. Configura las variables de entorno**

Crea un archivo `.env` en la raíz del proyecto:

```env
# Token del bot (obtenlo desde @BotFather en Telegram)
TELEGRAM_TOKEN=tu_token_aqui

# ID del administrador (opcional, para comandos restringidos)
ADMIN_ID=tu_id_aqui

# Ruta donde se guardan los archivos descargados temporalmente
DOWNLOAD_PATH=./downloads

# Tamaño máximo permitido para enviar por Telegram (en MB)
MAX_FILE_SIZE_MB=50

# Tiempo máximo de espera para una descarga (en segundos)
DOWNLOAD_TIMEOUT=300
```

> 💡 Obtén tu `TELEGRAM_TOKEN` hablando con [@BotFather](https://t.me/BotFather) en Telegram.  
> 💡 Tu `ADMIN_ID` lo puedes obtener con [@userinfobot](https://t.me/userinfobot).

**4. (Opcional) Instala ffmpeg**

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Descárgalo desde https://ffmpeg.org/download.html y agrégalo al PATH
```

**5. Ejecuta el bot**
```bash
python main.py
```

---

## 💬 Comandos disponibles

| Comando | Descripción |
|---|---|
| `/start` | Muestra el mensaje de bienvenida |
| `/download <url>` | Inicia la descarga de un video de YouTube |
| `/status` | Muestra métricas del servidor (CPU, RAM, disco) |

También puedes enviar un enlace de YouTube directamente al chat sin usar ningún comando.

---

## 🔄 Flujo de uso

```
Usuario envía URL
       ↓
Bot obtiene metadatos del video (título, duración, miniatura)
       ↓
Bot muestra los formatos disponibles como botones inline
       ↓
Usuario selecciona la calidad deseada
       ↓
Bot descarga y muestra el progreso en tiempo real
       ↓
Bot envía el archivo por Telegram y elimina el temporal
```

---

## 📦 Dependencias

| Paquete | Uso |
|---|---|
| `python-telegram-bot` | Framework del bot de Telegram |
| `yt-dlp` | Descarga y extracción de formatos de YouTube |
| `python-dotenv` | Carga de variables desde `.env` |
| `psutil` | Métricas del sistema para `/status` |
| `httpx` | Cliente HTTP asíncrono |

---

## ⚠️ Notas importantes

- El bot elimina automáticamente los archivos descargados tras enviarlos a Telegram.
- El límite de archivo de Telegram para bots es de **50 MB**. Configura `MAX_FILE_SIZE_MB` acorde a tu plan.
- Sin `ffmpeg`, solo se muestran formatos con video y audio ya combinados (generalmente calidad menor).
- Con `ffmpeg`, se ofrecen todas las resoluciones disponibles con audio de alta calidad.

---

## 📄 Licencia

MIT License — libre para usar, modificar y distribuir.
