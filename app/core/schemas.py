"""
Definición de los contratos de datos y esquemas de validación (Pydantic) para el pipeline de detección.
"""
from typing import Literal, Tuple, List
from uuid import uuid4
from pydantic import BaseModel, Field

class Detection(BaseModel):
    """Representa una detección de persona en un frame específico."""
    bbox: Tuple[float, float, float, float]  # (x1, y1, x2, y2)
    confidence: float = Field(ge=0.0, le=1.0)
    frame_index: int

class TrackedPerson(Detection):
    """Representa una persona detectada con un ID de tracking persistente."""
    track_id: int

class Keypoint(BaseModel):
    """Coordenadas de un punto de articulación (keypoint) y su confianza."""
    x: float
    y: float
    confidence: float = Field(ge=0.0, le=1.0)

class PoseResult(BaseModel):
    """Keypoints de interés (muñecas, codos, hombros y tobillos) asociados a un track ID."""
    track_id: int
    frame_index: int
    left_wrist: Keypoint
    right_wrist: Keypoint
    left_elbow: Keypoint
    right_elbow: Keypoint
    left_shoulder: Keypoint
    right_shoulder: Keypoint
    left_ankle: Keypoint
    right_ankle: Keypoint

class Zone(BaseModel):
    """Geometría de una zona de la góndola."""
    zone_id: str
    video_id: str
    name: str
    polygon: List[Tuple[float, float]]  # Puntos (x, y) que cierran la zona
    zone_type: Literal["product", "staff"] = "product"

class ZoneSignal(BaseModel):
    """Señales de interacción entre una persona trackeada y una zona en un frame."""
    track_id: int
    zone_id: str
    frame_index: int
    wrist_inside: bool
    arm_extended: bool

class InteractionEvent(BaseModel):
    """Evento final de interacción enviado al bus de eventos y guardado localmente."""
    event_type: Literal["interaction"] = "interaction"
    track_id: int
    zone_id: str
    # hoy el flujo real (state_machine.py) solo emite "taken"; los demás valores
    # están reservados para una iteración futura donde se distinga el tipo de interacción.
    action: Literal["reaching", "holding", "taken", "returned"]
    timestamp: float  # Segundos traducidos al video original
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    is_employee: bool = False


class PositionSample(BaseModel):
    """Posición estimada de los pies de una persona en un frame (coordenadas de píxel)."""
    event_type: Literal["position"] = "position"
    track_id: int
    frame_index: int
    timestamp: float
    x: float
    y: float
    source: Literal["ankle_keypoint", "bbox_bottom_center"]
    is_employee: bool = False
    event_id: str = Field(default_factory=lambda: str(uuid4()))


class DwellRecord(BaseModel):
    """Registro de tiempo de permanencia de una persona dentro de una zona de producto."""
    event_type: Literal["dwell"] = "dwell"
    track_id: int
    zone_id: str
    entry_timestamp: float
    exit_timestamp: float
    duration_sec: float
    is_employee: bool = False
    event_id: str = Field(default_factory=lambda: str(uuid4()))
