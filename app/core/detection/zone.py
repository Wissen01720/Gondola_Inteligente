"""
Gestión de zonas de góndola y operaciones geométricas.
"""
import json
import math
from pathlib import Path
from typing import List
from shapely.geometry import Point, Polygon

from app.core.detection.schemas import Zone, ZoneSignal, PoseResult, Keypoint
from app.utils.config import ZONES_STORAGE_PATH, ARM_EXTENSION_MIN_RATIO, MIN_KEYPOINT_CONFIDENCE

class ZoneManager:
    """Administra la carga y persistencia de las zonas de la góndola, agrupadas por video/cámara."""

    def __init__(self, storage_path: str = ZONES_STORAGE_PATH):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def save_zone(self, zone: Zone) -> None:
        """Guarda una zona en un archivo JSON, dentro de la subcarpeta de su video."""
        video_dir = self.storage_path / zone.video_id
        video_dir.mkdir(parents=True, exist_ok=True)
        file_path = video_dir / f"{zone.zone_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(zone.model_dump(), f, indent=4)

    def load_zones(self, video_id: str) -> List[Zone]:
        """Carga las zonas guardadas para un video/cámara específico (no mezcla con otros)."""
        zones = []
        video_dir = self.storage_path / video_id
        if not video_dir.exists():
            return zones
        for file_path in video_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    zones.append(Zone(**data))
            except Exception:
                # Silenciosamente omitir si el archivo está corrupto o no cumple el esquema
                pass
        return zones


def _euclidean_distance(kp1: Keypoint, kp2: Keypoint) -> float:
    """Calcula la distancia euclidiana entre dos keypoints."""
    return math.sqrt((kp1.x - kp2.x) ** 2 + (kp1.y - kp2.y) ** 2)


def check_zone_signal(pose: PoseResult, zones: List[Zone]) -> List[ZoneSignal]:
    """
    Chequea la posición de las muñecas respecto a las zonas y determina si el brazo está extendido.
    
    Heurística de brazo extendido:
    distancia(muñeca, hombro) / distancia(hombro, codo) >= ARM_EXTENSION_MIN_RATIO
    
    Se aplica filtro de confianza mínima de keypoints: ambas muñeca y hombro
    deben tener confianza >= MIN_KEYPOINT_CONFIDENCE para ser considerados válidos.
    """
    signals = []

    # Validar confianza de keypoints para brazo izquierdo
    left_valid = (pose.left_wrist.confidence >= MIN_KEYPOINT_CONFIDENCE and 
                  pose.left_shoulder.confidence >= MIN_KEYPOINT_CONFIDENCE)
    
    # Validar confianza de keypoints para brazo derecho
    right_valid = (pose.right_wrist.confidence >= MIN_KEYPOINT_CONFIDENCE and 
                   pose.right_shoulder.confidence >= MIN_KEYPOINT_CONFIDENCE)

    # Calcular distancias para brazo izquierdo (solo si es válido)
    left_extended = False
    if left_valid:
        left_wrist_shoulder = _euclidean_distance(pose.left_wrist, pose.left_shoulder)
        left_shoulder_elbow = _euclidean_distance(pose.left_shoulder, pose.left_elbow)
        if left_shoulder_elbow > 1e-5:
            left_extended = (left_wrist_shoulder / left_shoulder_elbow) >= ARM_EXTENSION_MIN_RATIO

    # Calcular distancias para brazo derecho (solo si es válido)
    right_extended = False
    if right_valid:
        right_wrist_shoulder = _euclidean_distance(pose.right_wrist, pose.right_shoulder)
        right_shoulder_elbow = _euclidean_distance(pose.right_shoulder, pose.right_elbow)
        if right_shoulder_elbow > 1e-5:
            right_extended = (right_wrist_shoulder / right_shoulder_elbow) >= ARM_EXTENSION_MIN_RATIO

    for zone in zones:
        if len(zone.polygon) < 3:
            continue
        
        poly = Polygon(zone.polygon)
        
        # Evaluar si la muñeca izquierda está adentro (solo si es válida)
        left_inside = False
        if left_valid:
            left_inside = Point(pose.left_wrist.x, pose.left_wrist.y).within(poly)
        
        # Evaluar si la muñeca derecha está adentro (solo si es válida)
        right_inside = False
        if right_valid:
            right_inside = Point(pose.right_wrist.x, pose.right_wrist.y).within(poly)
        
        wrist_inside = left_inside or right_inside
        
        # Determinar si el brazo que está adentro (o al menos uno si ambos) está extendido
        arm_extended = False
        if left_inside and left_extended:
            arm_extended = True
        if right_inside and right_extended:
            arm_extended = True

        signals.append(
            ZoneSignal(
                track_id=pose.track_id,
                zone_id=zone.zone_id,
                frame_index=pose.frame_index,
                wrist_inside=wrist_inside,
                arm_extended=arm_extended,
            )
        )

    return signals
