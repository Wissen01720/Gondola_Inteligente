"""
Mapeo y traducción de timestamps entre el video limpio y el original.
"""
from bisect import bisect_left
from typing import List, Dict, Tuple

# Cache: id(frame_mapping) -> (dict clean_frame->timestamp, frames ordenados, timestamps ordenados, len original)
# Nota de rendimiento: `translate_to_original_timestamp` se llama una vez por
# frame de video (ver pipeline.py). Antes reconstruía el dict completo en cada
# llamada (O(n) por frame => O(n^2) en el total del video). Como el pipeline
# reutiliza la MISMA lista `frame_mapping` durante toda la ejecución, cacheamos
# la estructura por id() de la lista y la reconstruimos solo si cambia de tamaño.
_mapping_cache: Dict[int, Tuple[Dict[int, float], List[int], List[float], int]] = {}


def _get_mapping_structures(frame_mapping: List[Dict]) -> Tuple[Dict[int, float], List[int], List[float]]:
    key = id(frame_mapping)
    cached = _mapping_cache.get(key)
    if cached is not None and cached[3] == len(frame_mapping):
        return cached[0], cached[1], cached[2]

    mapping = {item["clean_frame"]: item["original_timestamp_sec"] for item in frame_mapping}
    sorted_frames = sorted(mapping.keys())
    sorted_timestamps = [mapping[f] for f in sorted_frames]
    _mapping_cache[key] = (mapping, sorted_frames, sorted_timestamps, len(frame_mapping))
    return mapping, sorted_frames, sorted_timestamps


def translate_to_original_timestamp(clean_frame_index: int, frame_mapping: List[Dict]) -> float:
    """
    Traduce el índice de frame del video limpio al timestamp (segundos) del video original.
    Si el índice no existe exactamente, usa el frame más cercano (búsqueda binaria).
    """
    if not frame_mapping:
        return 0.0

    mapping, sorted_frames, sorted_timestamps = _get_mapping_structures(frame_mapping)

    if clean_frame_index in mapping:
        return float(mapping[clean_frame_index])

    # Búsqueda binaria del frame más cercano en vez de min() sobre toda la lista
    pos = bisect_left(sorted_frames, clean_frame_index)
    candidates = []
    if pos < len(sorted_frames):
        candidates.append(pos)
    if pos > 0:
        candidates.append(pos - 1)

    best_pos = min(candidates, key=lambda p: abs(sorted_frames[p] - clean_frame_index))
    return float(sorted_timestamps[best_pos])
