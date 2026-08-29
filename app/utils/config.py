"""
Configuración global del proyecto Scapder Vision.
Todos los parámetros ajustables viven aquí para no tocar código
cuando se necesite calibrar el sistema.
"""
from pathlib import Path

# ---- Rutas base ----
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
LOGS_DIR = DATA_DIR / "logs"

for d in (RAW_DIR, PROCESSED_DIR, LOGS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ---- Formatos soportados ----
SUPPORTED_VIDEO_EXTENSIONS = (".mp4", ".avi", ".mov", ".mkv", ".wmv")

# ---- Límites de carga (evitan que un video gigante o de horas tumbe la app) ----
# Duración máxima permitida en segundos. None = sin límite.
MAX_VIDEO_DURATION_SEC = 43200        # 12 horas

# Peso máximo permitido en MB. None = sin límite.
MAX_VIDEO_SIZE_MB = 10000             # 10 GB

# ---- Parámetros de limpieza de video ----
# FPS objetivo al reencodar (None = mantener el original)
DEFAULT_TARGET_FPS = None

# Resolución objetivo (ancho, alto). None = mantener original.
DEFAULT_TARGET_RESOLUTION = None

# Umbral de desviación estándar de intensidad para considerar un frame
# "congelado" o corrupto (frames casi idénticos consecutivos o pantalla negra)
FROZEN_FRAME_STD_THRESHOLD = 2.0
BLACK_FRAME_MEAN_THRESHOLD = 8.0

# Cuántos frames idénticos consecutivos se toleran antes de marcar como
# "cámara congelada" (posible corte de señal)
MAX_CONSECUTIVE_FROZEN_FRAMES = 15

# Codec de salida para los videos limpios
OUTPUT_CODEC = "mp4v"
OUTPUT_EXTENSION = ".mp4"
