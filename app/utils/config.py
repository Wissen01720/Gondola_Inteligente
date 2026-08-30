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

# --- Módulo 2: Detección, tracking y pose ---
DETECTION_MODEL_NAME = "yolo11n.pt"       # Modelo de detección de personas (pre-entrenado COCO)
POSE_MODEL_NAME = "yolo11n-pose.pt"       # Modelo de pose (pre-entrenado COCO-Keypoints)
DETECTION_CONF_THRESHOLD = 0.4            # Confianza mínima para aceptar una detección de persona
DETECTION_IOU_THRESHOLD = 0.5             # Umbral de IoU para NMS
TRACKER_CONFIG = "bytetrack.yaml"         # Tracker integrado de ultralytics

# --- Módulo 2: Zonas e interacción ---
ZONES_STORAGE_PATH = str(DATA_DIR / "zones") # Carpeta donde se guardan los polígonos de zona (.json)
ARM_EXTENSION_MIN_RATIO = 1.3             # Ratio distancia(muñeca,hombro)/longitud_antebrazo para considerar "brazo extendido"
MIN_KEYPOINT_CONFIDENCE = 0.3             # Confianza mínima de un keypoint para considerarlo válido en el cálculo geométrico

# --- Módulo 2: Emparejamiento pose <-> track ---
POSE_TRACK_MATCH_IOU_MIN = 0.25           # IoU mínimo entre bbox de pose y bbox de track para considerarlos la misma persona
POSE_TRACK_MATCH_MAX_DIST_SQ = 22500      # Distancia euclidiana al cuadrado (px^2) máxima como fallback si no hay solapamiento de IoU

# --- Módulo 2: Máquina de estados ---
MIN_FRAMES_REACHING_TO_HOLDING = 5        # Frames consecutivos en zona con brazo extendido antes de pasar a "holding"
MIN_FRAMES_HOLDING = 8                    # Frames mínimos en "holding" antes de poder emitir taken/returned
MAX_FRAMES_MISSING_TO_RESET = 10          # Frames sin detección de esa persona antes de resetear su estado a "idle"
MAX_SECONDS_STUCK_REACHING = 1.0          # Segundos con la muñeca dentro de la zona pero brazo no extendido antes de resetear a IDLE (evita "atascos")

# --- Módulo 2: Publicación de eventos ---
EVENT_PUBLISHER_MODE = "file"             # "file" | "stdout" | "websocket" (websocket aún no implementado, placeholder)
EVENTS_LOCAL_LOG_PATH = str(DATA_DIR / "events") # Carpeta de respaldo local mientras no hay transporte confirmado con Team 3

# Asegurar que existan los directorios
Path(ZONES_STORAGE_PATH).mkdir(parents=True, exist_ok=True)
Path(EVENTS_LOCAL_LOG_PATH).mkdir(parents=True, exist_ok=True)

