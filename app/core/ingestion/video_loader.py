"""
Carga de video y extracción de metadatos.
Esta capa NO hace UI ni limpieza: solo abre el archivo, valida que sea
legible y devuelve información estructurada (VideoInfo).
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2

from app.utils.config import (
    MAX_VIDEO_DURATION_SEC,
    MAX_VIDEO_SIZE_MB,
    SUPPORTED_VIDEO_EXTENSIONS,
)


@dataclass
class VideoInfo:
    path: Path
    filename: str
    duration_sec: float
    fps: float
    width: int
    height: int
    frame_count: int
    size_mb: float
    status: str = "cargado"          # cargado | limpiando | limpio | error
    error_message: Optional[str] = None
    thumbnail_path: Optional[Path] = None
    output_path: Optional[Path] = None
    cleaning_report: Optional[dict] = field(default=None)


class VideoLoadError(Exception):
    pass


def is_supported_video(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS


def load_video(path: str | Path) -> VideoInfo:
    """
    Abre el video, extrae metadatos básicos y hace una validación rápida
    de que el archivo realmente se puede leer (no está corrupto en el
    header, no está vacío, etc.). No recorre todos los frames.
    """
    path = Path(path)

    if not path.exists():
        raise VideoLoadError(f"El archivo no existe: {path}")

    if not is_supported_video(path):
        raise VideoLoadError(
            f"Formato no soportado: {path.suffix}. "
            f"Formatos válidos: {SUPPORTED_VIDEO_EXTENSIONS}"
        )

    size_mb = path.stat().st_size / (1024 * 1024)
    if MAX_VIDEO_SIZE_MB is not None and size_mb > MAX_VIDEO_SIZE_MB:
        raise VideoLoadError(
            f"El video pesa {size_mb:.1f} MB, supera el máximo permitido "
            f"de {MAX_VIDEO_SIZE_MB} MB: {path.name}"
        )

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        raise VideoLoadError(f"No se pudo abrir el video (posible corrupción): {path.name}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    # Intentar leer el primer frame para confirmar que el video es legible
    ok, frame = cap.read()
    if not ok or frame is None:
        cap.release()
        raise VideoLoadError(f"El video no tiene frames legibles: {path.name}")

    cap.release()

    if fps <= 0:
        # Algunos contenedores no reportan fps correctamente; usamos un
        # valor por defecto conservador para no dividir por cero después.
        fps = 25.0

    duration_sec = frame_count / fps if fps > 0 else 0.0

    if MAX_VIDEO_DURATION_SEC is not None and duration_sec > MAX_VIDEO_DURATION_SEC:
        raise VideoLoadError(
            f"El video dura {duration_sec:.0f}s, supera el máximo permitido "
            f"de {MAX_VIDEO_DURATION_SEC}s: {path.name}"
        )

    return VideoInfo(
        path=path,
        filename=path.name,
        duration_sec=duration_sec,
        fps=fps,
        width=width,
        height=height,
        frame_count=frame_count,
        size_mb=round(size_mb, 2),
    )


def extract_thumbnail(video_info: VideoInfo, output_path: Path, frame_position_ratio: float = 0.1) -> Path:
    """
    Extrae un frame representativo (por defecto al 10% del video) y lo
    guarda como imagen para usarlo de preview en la UI.
    """
    cap = cv2.VideoCapture(str(video_info.path))
    if not cap.isOpened():
        raise VideoLoadError(f"No se pudo reabrir el video para extraer miniatura: {video_info.filename}")

    target_frame = int(video_info.frame_count * frame_position_ratio)
    cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
    ok, frame = cap.read()
    cap.release()

    if not ok or frame is None:
        raise VideoLoadError(f"No se pudo extraer miniatura de: {video_info.filename}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), frame)
    return output_path
