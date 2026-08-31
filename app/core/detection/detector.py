"""
Detección de personas usando YOLOv8/v11 de Ultralytics.
"""
from typing import List
import numpy as np
from ultralytics import YOLO

from app.core.detection.schemas import Detection
from app.utils.config import DETECTION_MODEL_NAME, DETECTION_CONF_THRESHOLD, DETECTION_IOU_THRESHOLD

class PersonDetector:
    """Encapsula la carga e inferencia del modelo para detección de personas."""

    def __init__(self, model_name: str = DETECTION_MODEL_NAME):
        # Carga el modelo una sola vez al instanciar la clase
        self.model = YOLO(model_name)

    def detect(self, frame: np.ndarray, frame_index: int) -> List[Detection]:
        """
        Detecta personas en un frame (imagen numpy).
        Filtra por la clase 'persona' (COCO class id = 0) y el umbral de confianza.
        """
        # Inferencia
        # verbose=False para no inundar la consola de logs de ultralytics
        results = self.model(frame, iou=DETECTION_IOU_THRESHOLD, verbose=False)
        detections = []

        for result in results:
            if result.boxes is None:
                continue

            for box in result.boxes:
                # La clase persona en el dataset COCO es la clase 0
                cls_id = int(box.cls[0].item())
                if cls_id != 0:
                    continue

                conf = float(box.conf[0].item())
                if conf < DETECTION_CONF_THRESHOLD:
                    continue

                # xyxy es una tupla/lista [x1, y1, x2, y2]
                xyxy = box.xyxy[0].cpu().tolist()
                bbox = (xyxy[0], xyxy[1], xyxy[2], xyxy[3])

                detections.append(
                    Detection(
                        bbox=bbox,
                        confidence=conf,
                        frame_index=frame_index
                    )
                )

        return detections
