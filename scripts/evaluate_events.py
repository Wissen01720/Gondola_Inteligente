"""
Script de evaluación offline de precisión/recall de los InteractionEvent detectados.

Compara los eventos de interacción emitidos por el pipeline (archivo .jsonl generado
por LocalEventPublisher) contra un ground truth anotado a mano (CSV).

Limitaciones metodológicas:
- Es una evaluación OFFLINE con ground truth manual, sobre el video original.
- No reemplaza una validación estadística con más datos ni métricas por zona/persona.
- La tolerancia temporal (--tolerance-sec, default 2.0s) es una decisión de diseño:
  los timestamps de los eventos vienen de la traducción vía frame_mapping, no de un
  timestamp exacto al frame, así que existe ruido temporal propio del proceso. 2.0s
  es una ventana razonable para absorber ese ruido sin emparejar eventos espurios.

Solo usa librería estándar (argparse, csv, json, dataclasses, pathlib) para poder
correr sin depender del entorno virtual del proyecto.
"""

import argparse
import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class GroundTruth:
    """Un evento del ground truth anotado a mano."""
    timestamp: float
    zone_id: str
    track_id: str = ""   # informativo, opcional; NO se exige coincidir con el tracker
    action: str = "taken"


@dataclass
class MatchRecord:
    """Registro detallado de un emparejamiento para auditoría."""
    ground_truth_ts: float
    detected_ts: float
    zone_id: str
    delta_sec: float
    action_match: bool


def parse_args():
    parser = argparse.ArgumentParser(
        description="Calcula precision y recall de los InteractionEvent contra un ground truth manual."
    )
    parser.add_argument(
        "--ground-truth",
        type=str,
        required=True,
        help="CSV con columnas timestamp,zone_id,track_id,action (timestamp float en segundos del video original).",
    )
    parser.add_argument(
        "--events",
        type=str,
        required=True,
        help="Ruta al archivo .jsonl generado por LocalEventPublisher.",
    )
    parser.add_argument(
        "--tolerance-sec",
        type=float,
        default=2.0,
        help="Ventana de tolerancia temporal (seg) para considerar un match. Default: 2.0.",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default="",
        help="Opcional: ruta a un CSV de auditoría con cada match y cada evento sin emparejar (FP/FN).",
    )
    return parser.parse_args()


def load_ground_truth(path: Path) -> List[GroundTruth]:
    """Carga el CSV de ground truth. Accion por defecto 'taken' si viene vacia."""
    if not path.exists():
        raise FileNotFoundError(f"No se encontro el ground truth: {path}")

    gt = []
    with open(path, "r", encoding="utf-8") as f:
        # Saltar lineas de comentario y lineas en blanco
        raw = [line for line in f if line.strip() and not line.lstrip().startswith("#")]

    reader = csv.DictReader(raw)
    for row in reader:
        ts_raw = (row.get("timestamp", "") or "").strip()
        if not ts_raw:
            continue  # fila en blanco / final de archivo
        timestamp = float(ts_raw)
        zone_id = (row.get("zone_id", "") or "").strip()
        track_id = (row.get("track_id", "") or "").strip()
        action = ((row.get("action", "") or "").strip() or "taken")
        gt.append(GroundTruth(timestamp=timestamp, zone_id=zone_id, track_id=track_id, action=action))
    return gt


def load_detected_events(path: Path) -> List[dict]:
    """Carga los eventos .jsonl y se queda solo con los de tipo 'interaction'."""
    if not path.exists():
        raise FileNotFoundError(f"No se encontro el archivo de eventos: {path}")

    events = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Filtrar por discriminador event_type (fix Fase 4.1).
            if ev.get("event_type") == "interaction":
                events.append(ev)
    return events


def match_events(gt: List[GroundTruth], detected: List[dict], tolerance: float):
    """
    Emparejamiento greedy nearest-neighbor por zona (no Hungarian).

    Para cada evento del ground truth (ordenado por timestamp), se busca dentro de su
    mismo zone_id el evento detectado no usado cuya diferencia de timestamp sea minima
    y este dentro de --tolerance-sec.
    """
    # Agrupar detectados por zone_id, ordenados por timestamp
    by_zone: Dict[str, List[dict]] = {}
    for ev in detected:
        by_zone.setdefault(ev.get("zone_id", ""), []).append(ev)
    for zid in by_zone:
        by_zone[zid].sort(key=lambda e: float(e.get("timestamp", 0.0)))

    used: List[bool] = []
    merged_used: Dict[str, List[bool]] = {zid: [False] * len(zid_evs) for zid, zid_evs in by_zone.items()}

    matches: List[MatchRecord] = []
    false_negatives: List[GroundTruth] = []
    false_positives: List[dict] = []

    # Ordenar ground truth por timestamp
    for g in sorted(gt, key=lambda g: g.timestamp):
        candidates = by_zone.get(g.zone_id, [])
        best_idx = None
        best_delta = None
        for i, ev in enumerate(candidates):
            if merged_used[g.zone_id][i]:
                continue
            delta = abs(float(ev.get("timestamp", 0.0)) - g.timestamp)
            if delta <= tolerance:
                if best_delta is None or delta < best_delta:
                    best_delta = delta
                    best_idx = i

        if best_idx is not None:
            ev = candidates[best_idx]
            merged_used[g.zone_id][best_idx] = True
            matches.append(MatchRecord(
                ground_truth_ts=g.timestamp,
                detected_ts=float(ev.get("timestamp", 0.0)),
                zone_id=g.zone_id,
                delta_sec=best_delta,
                action_match=(ev.get("action", "") == g.action),
            ))
        else:
            false_negatives.append(g)

    # Detectados no usados = False Positives
    for zid, evs in by_zone.items():
        for i, ev in enumerate(evs):
            if not merged_used[zid][i]:
                false_positives.append(ev)

    return matches, false_negatives, false_positives


def safe_div(n, d):
    if d == 0:
        return 0.0
    return n / d


def main():
    args = parse_args()
    gt = load_ground_truth(Path(args.ground_truth))
    detected = load_detected_events(Path(args.events))

    matches, fn, fp = match_events(gt, detected, args.tolerance_sec)

    tp = len(matches)
    fn_count = len(fn)
    fp_count = len(fp)

    precision = safe_div(tp, tp + fp_count)
    recall = safe_div(tp, tp + fn_count)
    f1 = safe_div(2 * precision * recall, precision + recall) if (precision + recall) > 0 else 0.0

    action_matches = sum(1 for m in matches if m.action_match)
    pct_action_match = safe_div(action_matches, tp) * 100.0

    print("=" * 60)
    print("EVALUACION DE PRECISION / RECALL (InteractionEvent)")
    print("=" * 60)
    print(f"Ground truth:        {len(gt)} eventos")
    print(f"Detectados (total):  {len(detected)} eventos de interaccion")
    print(f"Tolerancia temporal: {args.tolerance_sec:.1f} s")
    print("-" * 60)
    print(f"{'TP':<6}{'FP':<6}{'FN':<6}")
    print(f"{tp:<6}{fp_count:<6}{fn_count:<6}")
    print("-" * 60)
    print(f"Precision = {precision:.3f}")
    print(f"Recall    = {recall:.3f}")
    print(f"F1        = {f1:.3f}")
    print(f"% matches con action_match=True = {pct_action_match:.1f}%")
    print("-" * 60)
    print("NOTA metodologica: el sistema actual no distingue pick-up vs put-back,")
    print("siempre emite action='taken' por diseno. Por eso action_match es solo")
    print("informativo y NO afecta si un evento cuenta como TP.")
    print("=" * 60)

    if args.output_csv:
        with open(args.output_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["tipo", "ground_truth_ts", "detected_ts", "zone_id", "delta_sec", "action_match"])
            for m in matches:
                writer.writerow(["match", m.ground_truth_ts, m.detected_ts, m.zone_id,
                                 f"{m.delta_sec:.3f}", "1" if m.action_match else "0"])
            for g in fn:
                writer.writerow(["FN", g.timestamp, "", g.zone_id, "", ""])
            for ev in fp:
                writer.writerow(["FP", "", ev.get("timestamp", ""), ev.get("zone_id", ""), "", ""])
        print(f"Auditoria exportada a: {args.output_csv}")


if __name__ == "__main__":
    main()
