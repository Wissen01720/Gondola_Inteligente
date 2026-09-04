"""
Ventana principal.

Diseñada como QTabWidget para que agregar módulos futuros (detección,
tracking, dashboard de métricas) sea simplemente crear una nueva pestaña,
sin tocar esta clase más allá de una línea en __init__.
"""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.ingestion.video_loader import VideoInfo, VideoLoadError, extract_thumbnail, load_video
from app.core.ingestion.workers import VideoCleaningWorker
from app.ui.zone_editor_tab import ZoneEditorTab
from app.utils import config


class VideoIngestTab(QWidget):
    """Pestaña 1: Carga y limpieza de video."""

    def __init__(self):
        super().__init__()
        self.videos: dict[str, VideoInfo] = {}
        self.worker: VideoCleaningWorker | None = None
        self._build_ui()

    # ---------------------------------------------------------------- UI --
    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Barra de acciones ---
        actions_layout = QHBoxLayout()
        self.btn_load = QPushButton("📁 Cargar video(s)")
        self.btn_load.clicked.connect(self.on_load_videos)
        self.btn_clean = QPushButton("🧹 Limpiar seleccionados")
        self.btn_clean.clicked.connect(self.on_clean_videos)
        self.btn_clean.setEnabled(False)
        self.btn_clean_all = QPushButton("🧹 Limpiar todos")
        self.btn_clean_all.clicked.connect(self.on_clean_all)
        self.btn_clean_all.setEnabled(False)

        actions_layout.addWidget(self.btn_load)
        actions_layout.addWidget(self.btn_clean)
        actions_layout.addWidget(self.btn_clean_all)
        actions_layout.addStretch()
        main_layout.addLayout(actions_layout)

        # --- Zona central: lista + preview ---
        splitter = QSplitter(Qt.Horizontal)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        splitter.addWidget(self.list_widget)

        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        self.thumbnail_label = QLabel("Selecciona un video para ver su vista previa")
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setMinimumSize(360, 240)
        self.thumbnail_label.setStyleSheet("border: 1px solid #444; background: #1e1e1e; color: #999;")
        self.metadata_label = QLabel("")
        self.metadata_label.setWordWrap(True)
        preview_layout.addWidget(self.thumbnail_label)
        preview_layout.addWidget(self.metadata_label)
        preview_layout.addStretch()
        splitter.addWidget(preview_container)

        splitter.setSizes([320, 480])
        main_layout.addWidget(splitter, stretch=1)

        # --- Barra de progreso + log ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(140)
        main_layout.addWidget(self.log_area)

    # ---------------------------------------------------------- callbacks --
    def on_load_videos(self):
        extensions = " ".join(f"*{ext}" for ext in config.SUPPORTED_VIDEO_EXTENSIONS)
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Seleccionar videos", str(Path.home()), f"Videos ({extensions})"
        )
        if not paths:
            return

        for path_str in paths:
            path = Path(path_str)
            try:
                video_info = load_video(path)
            except VideoLoadError as exc:
                self._log(f"❌ {path.name}: {exc}")
                continue

            self.videos[video_info.filename] = video_info

            item = QListWidgetItem(f"✅ {video_info.filename}  ({video_info.duration_sec:.1f}s)")
            item.setData(Qt.UserRole, video_info.filename)
            self.list_widget.addItem(item)
            self._log(f"Cargado: {video_info.filename} — {video_info.width}x{video_info.height} @ {video_info.fps:.1f}fps")

        self.btn_clean.setEnabled(len(self.videos) > 0)
        self.btn_clean_all.setEnabled(len(self.videos) > 0)

    def _on_selection_changed(self):
        items = self.list_widget.selectedItems()
        if not items:
            return
        filename = items[0].data(Qt.UserRole)
        video_info = self.videos.get(filename)
        if not video_info:
            return

        thumb_path = config.LOGS_DIR / f"{Path(filename).stem}_thumb.jpg"
        try:
            if not thumb_path.exists():
                extract_thumbnail(video_info, thumb_path)
            pixmap = QPixmap(str(thumb_path)).scaled(
                self.thumbnail_label.width(), self.thumbnail_label.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
            self.thumbnail_label.setPixmap(pixmap)
        except VideoLoadError as exc:
            self.thumbnail_label.setText(f"Sin vista previa: {exc}")

        status_line = f"Estado: {video_info.status}"
        if video_info.cleaning_report:
            r = video_info.cleaning_report
            status_line += (
                f"\nFrames leídos: {r['frames_read']} | escritos: {r['frames_written']}"
                f"\nNegros removidos: {r['black_frames_removed']} | congelados removidos: {r['frozen_frames_removed']}"
            )

        self.metadata_label.setText(
            f"<b>{video_info.filename}</b><br>"
            f"Resolución: {video_info.width}x{video_info.height}<br>"
            f"FPS: {video_info.fps:.2f}<br>"
            f"Duración: {video_info.duration_sec:.1f} s<br>"
            f"Tamaño: {video_info.size_mb} MB<br>"
            f"{status_line}"
        )

    def on_clean_videos(self):
        items = self.list_widget.selectedItems()
        if not items:
            QMessageBox.information(self, "Sin selección", "Selecciona al menos un video de la lista.")
            return
        filenames = [item.data(Qt.UserRole) for item in items]
        self._run_cleaning([self.videos[f] for f in filenames])

    def on_clean_all(self):
        if not self.videos:
            return
        self._run_cleaning(list(self.videos.values()))

    def _run_cleaning(self, videos_to_clean: list[VideoInfo]):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "En proceso", "Ya hay una limpieza en curso, espera a que termine.")
            return

        self.btn_load.setEnabled(False)
        self.btn_clean.setEnabled(False)
        self.btn_clean_all.setEnabled(False)
        self.progress_bar.setValue(0)

        self.worker = VideoCleaningWorker(videos_to_clean)
        self.worker.progress_updated.connect(self._on_progress)
        self.worker.video_finished.connect(self._on_video_finished)
        self.worker.video_failed.connect(self._on_video_failed)
        self.worker.all_finished.connect(self._on_all_finished)
        self.worker.start()

        self._log(f"Iniciando limpieza de {len(videos_to_clean)} video(s)...")

    def _on_progress(self, filename: str, current: int, total: int):
        pct = int((current / total) * 100) if total else 0
        self.progress_bar.setValue(pct)

    def _on_video_finished(self, filename: str, report: dict):
        video_info = self.videos[filename]
        video_info.status = "limpio"
        video_info.cleaning_report = report
        video_info.output_path = Path(report["output_path"])

        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.UserRole) == filename:
                item.setText(f"🟢 {filename}  (limpio → {video_info.output_path.name})")

        self._log(
            f"✅ {filename} limpio: {report['frames_written']} frames útiles, "
            f"{report['black_frames_removed']} negros y {report['frozen_frames_removed']} congelados removidos."
        )

    def _on_video_failed(self, filename: str, error: str):
        video_info = self.videos.get(filename)
        if video_info:
            video_info.status = "error"
            video_info.error_message = error
        self._log(f"❌ Falló limpieza de {filename}: {error}")

    def _on_all_finished(self):
        self.btn_load.setEnabled(True)
        self.btn_clean.setEnabled(True)
        self.btn_clean_all.setEnabled(True)
        self.progress_bar.setValue(100)
        self._log("Proceso de limpieza finalizado.")

    def _log(self, message: str):
        self.log_area.append(message)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Scapder Vision — Prototipo de Space Management")
        self.resize(1100, 700)

        tabs = QTabWidget()
        tabs.addTab(VideoIngestTab(), "1. Carga y Limpieza de Video")
        tabs.addTab(ZoneEditorTab(), "2. Edición de Zonas (ROI)")
        # Futuras pestañas (ya con el espacio reservado en la arquitectura):
        # tabs.addTab(DetectionTab(), "3. Detección y Tracking")
        # tabs.addTab(InteractionTab(), "4. Eventos de Interacción")
        # tabs.addTab(DashboardTab(), "5. Dashboard de Métricas")

        self.setCentralWidget(tabs)
