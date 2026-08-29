"""
Workers de QThread. Cualquier tarea pesada (limpieza de video, y en el
futuro: detección, tracking) debe correr aquí, nunca en el hilo de UI.
"""
from PySide6.QtCore import QThread, Signal

from app.core.video_cleaner import clean_video
from app.core.video_loader import VideoInfo


class VideoCleaningWorker(QThread):
    progress_updated = Signal(str, int, int)   # filename, frame_actual, frame_total
    video_finished = Signal(str, dict)         # filename, reporte como dict
    video_failed = Signal(str, str)            # filename, mensaje de error
    all_finished = Signal()

    def __init__(self, videos: list[VideoInfo], parent=None):
        super().__init__(parent)
        self.videos = videos

    def run(self):
        for video_info in self.videos:
            filename = video_info.filename
            try:
                def _on_progress(current, total, fn=filename):
                    self.progress_updated.emit(fn, current, total)

                report = clean_video(video_info, progress_callback=_on_progress)
                self.video_finished.emit(filename, report.as_dict())
            except Exception as exc:  # noqa: BLE001 - queremos capturar cualquier fallo por video
                self.video_failed.emit(filename, str(exc))

        self.all_finished.emit()
