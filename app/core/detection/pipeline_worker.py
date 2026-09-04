"""
Worker de QThread para el pipeline de detección (Team 2).

Espejo del patrón de `app/core/ingestion/workers.py` (VideoCleaningWorker):
el pipeline corre en un hilo de fondo para que la publicación frecuente de
eventos (sobre todo el stream de `PositionSample`) nunca bloquee el hilo de
UI. Las señales Qt del `InProcessPublisher` llegan al hilo principal
automáticamente (conexiones en cola).
"""
from PySide6.QtCore import QThread, Signal

from app.core.detection.pipeline import DetectionPipeline
from app.core.ingestion.frame_source import FrameSource


class DetectionPipelineWorker(QThread):
    progress_updated = Signal(int)   # frames procesados hasta ahora
    pipeline_finished = Signal(int)  # frames totales procesados
    pipeline_failed = Signal(str)    # mensaje de error

    def __init__(self, pipeline: DetectionPipeline, source: FrameSource, parent=None):
        super().__init__(parent)
        self.pipeline = pipeline
        self.source = source
        self._frames_processed = 0

    def run(self):
        try:
            # pipeline.run() cierra la fuente al terminar (finally)
            self.pipeline.run(self.source, progress_callback=self._on_progress)
            self.pipeline_finished.emit(self._frames_processed)
        except Exception as exc:  # noqa: BLE001 - reportar cualquier fallo del pipeline
            self.pipeline_failed.emit(str(exc))

    def _on_progress(self, frame_index: int):
        self._frames_processed = frame_index
        self.progress_updated.emit(frame_index)