"""
Estimador híbrido de posición de pies de una persona.
Dado un TrackedPerson y opcionalmente su PoseResult, devuelve la mejor
estimación disponible del punto donde la persona toca el suelo.
"""
from typing import Optional

from app.core.schemas import TrackedPerson, PoseResult, PositionSample
from app.utils.config import MIN_KEYPOINT_CONFIDENCE


def estimate_foot_position(
    tracked_person: TrackedPerson,
    pose: Optional[PoseResult],
    frame_index: int,
    timestamp: float,
) -> PositionSample:
    """
    Estima la posición de los pies de una persona.

    Prioriza los tobillos de la pose si están disponibles con suficiente confianza;
    si no, usa el centro inferior del bounding box como respaldo.
    """
    ankle_x, ankle_y = None, None
    source = "bbox_bottom_center"

    if pose is not None:
        left_ok = pose.left_ankle.confidence >= MIN_KEYPOINT_CONFIDENCE
        right_ok = pose.right_ankle.confidence >= MIN_KEYPOINT_CONFIDENCE

        if left_ok and right_ok:
            ankle_x = (pose.left_ankle.x + pose.right_ankle.x) / 2.0
            ankle_y = (pose.left_ankle.y + pose.right_ankle.y) / 2.0
            source = "ankle_keypoint"
        elif left_ok:
            ankle_x = pose.left_ankle.x
            ankle_y = pose.left_ankle.y
            source = "ankle_keypoint"
        elif right_ok:
            ankle_x = pose.right_ankle.x
            ankle_y = pose.right_ankle.y
            source = "ankle_keypoint"

    if ankle_x is not None and ankle_y is not None:
        x, y = ankle_x, ankle_y
    else:
        x1, y1, x2, y2 = tracked_person.bbox
        x = (x1 + x2) / 2.0
        y = y2

    return PositionSample(
        track_id=tracked_person.track_id,
        frame_index=frame_index,
        timestamp=timestamp,
        x=x,
        y=y,
        source=source,
    )
