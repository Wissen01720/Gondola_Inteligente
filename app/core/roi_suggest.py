"""
Sugerencia automática de zonas de interés (ROI) usando visión clásica (Canny + contornos).

ADVERTENCIA: esto es una heurística sin entrenamiento, que puede fallar o sugerir
candidatos irrelevantes (productos individuales, sombras, reflejos). El usuario
siempre tiene la última palabra dibujando manualmente encima o ignorando las sugerencias.
"""
from typing import List, Tuple

import cv2
import numpy as np

from app.utils.config import (
    ROI_SUGGEST_CANNY_THRESHOLD_1,
    ROI_SUGGEST_CANNY_THRESHOLD_2,
    ROI_SUGGEST_MIN_AREA_RATIO,
    ROI_SUGGEST_MIN_ASPECT_RATIO,
    ROI_SUGGEST_MAX_ASPECT_RATIO,
    ROI_SUGGEST_MAX_CANDIDATES,
)


def suggest_zone_candidates(frame: np.ndarray) -> List[List[Tuple[int, int]]]:
    """
    Detecta candidatos a zonas de interés en un frame usando detección de bordes.

    Devuelve como máximo ROI_SUGGEST_MAX_CANDIDATES polígonos rectangulares
    ordenados por área descendente, cada uno como lista de 4 puntos [(x1,y1),...].
    """
    h, w = frame.shape[:2]
    frame_area = float(h * w)

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, ROI_SUGGEST_CANNY_THRESHOLD_1, ROI_SUGGEST_CANNY_THRESHOLD_2)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        area = float(bw * bh)
        if area / frame_area < ROI_SUGGEST_MIN_AREA_RATIO:
            continue

        aspect = bw / bh if bh > 0 else 0.0
        inv_aspect = bh / bw if bw > 0 else 0.0
        if not (ROI_SUGGEST_MIN_ASPECT_RATIO <= aspect <= ROI_SUGGEST_MAX_ASPECT_RATIO):
            if not (ROI_SUGGEST_MIN_ASPECT_RATIO <= inv_aspect <= ROI_SUGGEST_MAX_ASPECT_RATIO):
                continue

        candidates.append((area, x, y, bw, bh))

    candidates.sort(key=lambda c: c[0], reverse=True)
    candidates = candidates[:ROI_SUGGEST_MAX_CANDIDATES]

    result = []
    for _, x, y, bw, bh in candidates:
        poly = [
            (x, y),
            (x + bw, y),
            (x + bw, y + bh),
            (x, y + bh),
        ]
        result.append(poly)

    return result
