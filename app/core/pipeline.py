"""
Orquestador principal del pipeline de detección de Scapder Vision.
"""
import json
from pathlib import Path
from typing import List, Optional, Dict
import cv2

from app.core.tracker import PersonTracker
from app.core.pose import PoseEstimator
from app.core.zone import ZoneManager, check_zone_signal
from app.core.state_machine import InteractionStateMachine
from app.core.event_publisher import EventPublisher
from app.core.frame_mapping import translate_to_original_timestamp
from app.core.position import estimate_foot_position
from app.core.presence import DwellTracker
from app.core.staff import StaffZoneTracker

class DetectionPipeline:
    """Orquesta el flujo de tracking, pose, validación de zonas, traducción y envío de eventos."""

    def __init__(
        self,
        tracker: PersonTracker,
        pose_estimator: PoseEstimator,
        zone_manager: ZoneManager,
        state_machine: InteractionStateMachine,
        event_publisher: EventPublisher,
        frame_mapping: Optional[List[Dict]] = None,
        dwell_tracker: Optional[DwellTracker] = None,
        staff_tracker: Optional[StaffZoneTracker] = None,
    ):
        self.tracker = tracker
        self.pose_estimator = pose_estimator
        self.zone_manager = zone_manager
        self.state_machine = state_machine
        self.event_publisher = event_publisher
        self.frame_mapping = frame_mapping
        self.dwell_tracker = dwell_tracker or DwellTracker()
        self.staff_tracker = staff_tracker or StaffZoneTracker()

    def run(self, video_path: str) -> None:
        """
        Ejecuta el pipeline sobre un archivo de video.
        Abre el video, procesa cada frame de punta a punta y publica cada evento a medida que se genera durante el recorrido.
        """
        video_path_obj = Path(video_path)
        if not video_path_obj.exists():
            raise FileNotFoundError(f"No se encontró el video: {video_path}")

        # Intentar cargar el frame mapping si no se pasó
        if self.frame_mapping is None:
            json_path = video_path_obj.with_suffix(".json")
            if json_path.exists():
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        report_data = json.load(f)
                        self.frame_mapping = report_data.get("frame_mapping", [])
                except Exception as e:
                    print(f"Advertencia: No se pudo leer el mapeo de frames desde {json_path}: {e}")
            
            if not self.frame_mapping:
                print("Advertencia: Ejecutando sin mapeo de frames. Los timestamps serán aproximados al frame rate del video limpio.")

        # Cargar las zonas del video actual (nombre del archivo sin extensión)
        video_id = video_path_obj.stem
        zones = self.zone_manager.load_zones(video_id)
        if not zones:
            print(f"Advertencia: No hay zonas de góndola definidas en {self.zone_manager.storage_path}")

        # Abrir captura de video
        cap = cv2.VideoCapture(str(video_path_obj))
        if not cap.isOpened():
            raise IOError(f"No se pudo abrir el archivo de video: {video_path}")

        # Obtener FPS y frame mapping de respaldo en caso de que falte
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

        frame_index = 0
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # 1. Trackear personas
                tracked_people = self.tracker.track(frame, frame_index)

                # 2. Estimar Pose
                pose_results = self.pose_estimator.estimate(frame, frame_index, tracked_people)

                # 2.5 Calcular timestamp una sola vez por frame
                if self.frame_mapping:
                    current_timestamp = translate_to_original_timestamp(frame_index, self.frame_mapping)
                else:
                    current_timestamp = frame_index / fps

                # 2.6 Estimar posición de pies, detectar staff y medir dwell time
                pose_by_track = {p.track_id: p for p in pose_results}
                for person in tracked_people:
                    pose_o = pose_by_track.get(person.track_id)
                    position_sample = estimate_foot_position(
                        person, pose_o, frame_index, current_timestamp,
                    )
                    is_emp = self.staff_tracker.update(position_sample, zones)
                    position_sample.is_employee = is_emp
                    self.event_publisher.publish(position_sample)

                    dwell_records = self.dwell_tracker.update(
                        position_sample, zones, current_timestamp,
                    )
                    for dwell_record in dwell_records:
                        dwell_record.is_employee = self.staff_tracker.is_employee(dwell_record.track_id)
                        self.event_publisher.publish(dwell_record)

                # 3. Calcular señales de zona
                all_signals = []
                for pose in pose_results:
                    signals = check_zone_signal(pose, zones)
                    all_signals.extend(signals)

                # 4. Pasar señales a la máquina de estados
                events = self.state_machine.process(all_signals)

                # 5. Traducir timestamps y publicar eventos
                for event in events:
                    event.timestamp = current_timestamp
                    event.is_employee = self.staff_tracker.is_employee(event.track_id)
                    self.event_publisher.publish(event)

                frame_index += 1
        finally:
            cap.release()
            print(f"Procesamiento completado. Se procesaron {frame_index} frames.")
