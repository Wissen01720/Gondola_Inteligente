"""
Fuentes de frames para el pipeline de detección (Team 1).

Abstracción que desacopla el pipeline del tipo de entrada:

- `VideoFileFrameSource`: video limpio de `data/processed/` con su
  `frame_mapping.json` al lado — traduce el timestamp de cada frame al
  video original reutilizando `app.core.detection.frame_mapping` (no se
  duplica esa lógica aquí).
- `LiveFrameSource`: stub para cámara en vivo (webcam/RTSP). No hay
  "video original" al que mapear: los timestamps son wall-clock y
  pasan tal cual. Lo implementa Team 1 en una iteración futura.

El pipeline solo consume `FrameSource`, así que el resto del sistema
no sabe ni le importa si el origen es archivo o cámara.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union
import json

import cv2
import numpy as np

from app.core.detection.frame_mapping import translate_to_original_timestamp


@dataclass
class FrameSample:
    """Un frame listo para procesar, con su índice y timestamp resuelto."""
    frame: np.ndarray
    frame_index: int
    timestamp_sec: float  # Segundos en el video original (o wall-clock en vivo)


class FrameSource(ABC):
    """Interfaz de fuente de frames: el pipeline itera con `next_frame()`."""

    @property
    @abstractmethod
    def fps(self) -> float:
        """Frames por segundo del stream (usado para la máquina de estados)."""
        pass

    @abstractmethod
    def next_frame(self) -> Optional[FrameSample]:
        """Devuelve el siguiente frame o None cuando el stream se agota."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Libera recursos (cap, socket, etc.)."""
        pass


class VideoFileFrameSource(FrameSource):
    """Lector de video limpio + `frame_mapping.json` (Módulo 1).

    Si no se pasa `frame_mapping`, intenta cargar el `.json` con el mismo
    nombre que el video. Si tampoco existe, los timestamps caen a un
    fallback por FPS (comportamiento actual del pipeline).
    """

    def __init__(
        self,
        video_path: Union[str, Path],
        frame_mapping: Optional[List[Dict]] = None,
        fps: Optional[float] = None,
    ):
        video_path_obj = Path(video_path)
        if not video_path_obj.exists():
            raise FileNotFoundError(f"No se encontró el video: {video_path}")

        self.video_path = video_path_obj
        self.cap = cv2.VideoCapture(str(video_path_obj))
        if not self.cap.isOpened():
            raise IOError(f"No se pudo abrir el archivo de video: {video_path}")

        self._fps = fps or (self.cap.get(cv2.CAP_PROP_FPS) or 30.0)

        # Cargar el frame_mapping si no se pasó explícitamente
        if frame_mapping is None:
            json_path = video_path_obj.with_suffix(".json")
            if json_path.exists():
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        self.frame_mapping = json.load(f).get("frame_mapping", [])
                except Exception as e:
                    print(f"Advertencia: No se pudo leer el mapeo de frames desde {json_path}: {e}")
                    self.frame_mapping = []
            else:
                self.frame_mapping = []
        else:
            self.frame_mapping = frame_mapping

        if not self.frame_mapping:
            print(
                "Advertencia: Ejecutando sin mapeo de frames. "
                "Los timestamps serán aproximados al frame rate del video limpio."
            )

        self._frame_index = 0

    @property
    def fps(self) -> float:
        return self._fps

    def next_frame(self) -> Optional[FrameSample]:
        ret, frame = self.cap.read()
        if not ret:
            return None

        frame_index = self._frame_index
        self._frame_index += 1

        if self.frame_mapping:
            timestamp_sec = translate_to_original_timestamp(frame_index, self.frame_mapping)
        else:
            timestamp_sec = frame_index / self._fps

        return FrameSample(frame=frame, frame_index=frame_index, timestamp_sec=timestamp_sec)

    def close(self) -> None:
        self.cap.release()


class LiveFrameSource(FrameSource):
    """Stub de cámara en vivo (webcam/RTSP) — lo implementa Team 1.

    Diseño: sin `frame_mapping` (no hay video original que mapear); el
    `timestamp_sec` de cada FrameSample es wall-clock (monotónico) y el
    pipeline lo usa tal cual. Los eventos/position samples quedan entonces
    referenciados al reloj de la sesión en vivo.
    """

    def __init__(self, source_id: str = "webcam_0"):
        self.source_id = source_id
        self._fps = 30.0  # TODO(Team 1): leer FPS real de la cámara/RTSP

    @property
    def fps(self) -> float:
        return self._fps

    def next_frame(self) -> Optional[FrameSample]:
        # TODO(Team 1): abrir webcam/RTSP (cv2.VideoCapture) y devolver el
        # frame con timestamp wall-clock. Por ahora es un stub deliberado.
        raise NotImplementedError(
            "LiveFrameSource aún no implementado — pendiente de Team 1 "
            "(integración webcam/RTSP)."
        )

    def close(self) -> None:
        # TODO(Team 1): liberar la captura de cámara.
        pass