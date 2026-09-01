"""
Script de ayuda para dibujar zonas de góndola haciendo click (temporal).

Permite definir zonas manualmente sobre el primer frame de un video hasta que
Team 4 provea la herramienta real. No la reemplaza.

Uso:
    uv run python -m scripts.draw_zone_helper --video data/processed/<archivo>.mp4 \
        --zone-id zone_1 --name "Estanteria Principal" --zone-type product

Opcional (--auto-suggest):
    uv run python -m scripts.draw_zone_helper --video data/processed/<archivo>.mp4 \
        --zone-id zone_1 --name "Estanteria Principal" --zone-type product --auto-suggest

Instrucciones:
    - Click izquierdo: agrega un punto del polígono (en orden).
    - 's' (save): guarda la zona si hay al menos 3 puntos.
    - 'r' (reset): borra los puntos capturados y permite empezar de nuevo.
    - 'q' (quit): cierra sin guardar.
"""
import argparse
from pathlib import Path

import cv2

from app.core.schemas import Zone
from app.core.zone import ZoneManager


def parse_args():
    parser = argparse.ArgumentParser(description="Dibuja zonas de góndola por click sobre el primer frame del video.")
    parser.add_argument("--video", type=str, required=True, help="Ruta al video limpio (.mp4).")
    parser.add_argument("--zone-id", type=str, required=True, help="Identificador de la zona (ej. zone_1).")
    parser.add_argument("--name", type=str, required=True, help="Nombre descriptivo de la zona.")
    parser.add_argument("--zone-type", type=str, default="product", help="Tipo de zona (por defecto: product).")
    parser.add_argument("--auto-suggest", action="store_true", default=False, help="Sugerir zonas automáticamente usando visión clásica.")
    return parser.parse_args()


def main():
    args = parse_args()

    video_path = Path(args.video)
    if not video_path.exists():
        print(f"Error: No se encontró el video {video_path}")
        return
    video_id = video_path.stem

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"Error: No se pudo abrir el video {video_path}")
        return

    ret, frame = cap.read()
    cap.release()
    if not ret:
        print("Error: No se pudo extraer el primer frame del video.")
        return

    canvas = frame.copy()
    points = []
    window_name = f"Dibujar zona: {args.name}"
    suggestions = []

    if args.auto_suggest:
        from app.core.roi_suggest import suggest_zone_candidates
        suggestions = suggest_zone_candidates(frame)

    def redraw():
        nonlocal canvas
        canvas = frame.copy()

        # Dibujar sugerencias en naranja si existen
        for idx, sug in enumerate(suggestions):
            pts = [(int(x), int(y)) for x, y in sug]
            for i in range(len(pts)):
                cv2.line(canvas, pts[i], pts[(i + 1) % len(pts)], (0, 165, 255), 2)
            cv2.putText(canvas, str(idx + 1), (pts[0][0] - 5, pts[0][1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)

        for i, (x, y) in enumerate(points):
            cv2.circle(canvas, (x, y), 5, (0, 0, 255), -1)
            if i > 0:
                cv2.line(canvas, points[i - 1], (x, y), (0, 255, 0), 2)
            cv2.putText(canvas, str(i + 1), (x + 8, y - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        overlay_text = f"Puntos: {len(points)} | click=agregar, s=guardar, r=reset, q=salir"
        if suggestions:
            overlay_text += " | 1/2/3=aceptar sugerencia"
        cv2.putText(canvas, overlay_text, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.imshow(window_name, canvas)

    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            points.append((int(x), int(y)))
            redraw()

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window_name, on_mouse)
    redraw()

    saved_path = None
    while True:
        key = cv2.waitKey(20) & 0xFF
        if key == ord("s"):
            if len(points) < 3:
                print(f"Se necesitan al menos 3 puntos para guardar la zona (tienes {len(points)}).")
                continue
            zone = Zone(
                zone_id=args.zone_id,
                video_id=video_id,
                name=args.name,
                polygon=points,
                zone_type=args.zone_type,
            )
            manager = ZoneManager()
            saved_path = manager.save_zone(zone)
            print(f"Zona guardada en: {saved_path}")
        elif key == ord("r"):
            points.clear()
            redraw()
            print("Puntos borrados. Empieza de nuevo.")
        elif key == ord("q"):
            break
        elif key in (ord("1"), ord("2"), ord("3")):
            idx = key - ord("1")
            if idx < len(suggestions):
                points.clear()
                for x, y in suggestions[idx]:
                    points.append((int(x), int(y)))
                redraw()
                print(f"Sugerencia {idx + 1} cargada. Puedes ajustar con clicks o guardar con 's'.")

    cv2.destroyAllWindows()

    if saved_path is not None:
        print(f"Archivo de zona guardado en: {saved_path}")
    else:
        print("No se guardó ninguna zona.")


if __name__ == "__main__":
    main()
