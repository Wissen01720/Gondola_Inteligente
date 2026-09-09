"""
Ventana principal.

Diseñada como QTabWidget para que agregar módulos futuros sea
simplemente crear una nueva pestaña, sin tocar esta clase más allá de
una línea en __init__.
"""
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.ingestion.video_loader import VideoInfo, VideoLoadError, extract_thumbnail, load_video
from app.core.ingestion.workers import VideoCleaningWorker
from app.ui.dialogs.cut_video_dialog import CutVideoDialog
from app.ui.widgets.footer import FooterBar
from app.ui.widgets.header import HeaderBar
from app.ui.dashboard_tab import DashboardTab
from app.ui.zone_editor_tab import ZoneEditorTab
from app.utils import config


class VideoIngestTab(QWidget):

    def __init__(self):
        super().__init__()
        self.videos: dict[str, VideoInfo] = {}
        self.worker: VideoCleaningWorker | None = None
        self._source_type = "ip_camera"  # "ip_camera" | "file_upload"

        # Se mantienen para no romper la lógica de preview/limpieza existente,
        # aunque este mockup (Source Setup & Configuration) no los muestra.
        self.thumbnail_label = QLabel()
        self.metadata_label = QLabel()

        self._build_ui()

    # ---------------------------------------------------------------- UI --
    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Header --- (sin botón de acción: no había ninguna "Configuración"
        # real conectada a él en esta pestaña)
        self.header = HeaderBar("VISION_CORE_05", show_action=False)
        main_layout.addWidget(self.header)

        # --- Cuerpo: dos columnas ---
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(12, 12, 12, 12)
        body_layout.setSpacing(12)
        # Columna de archivos angosta (franja, como el rojo de la
        # referencia) y columna de video dominante (como el azul) —
        # antes era 1:2, ahora 1:3 para acentuar más la diferencia.
        body_layout.addWidget(self._build_left_column(), stretch=1)
        body_layout.addWidget(self._build_right_column(), stretch=3)
        main_layout.addWidget(body, stretch=1)

        # --- Footer ---
        self.footer = FooterBar()
        main_layout.addWidget(self.footer)

    def _build_left_column(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Archivos recientemente analizados")
        title.setObjectName("sectionTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

        # stretch=3: la lista es ahora el elemento dominante de la
        # columna (antes competía en espacio con el VideoInfoPanel).
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.list_widget.setSpacing(6)  # más aire entre cada video de la lista
        self.list_widget.setStyleSheet("QListWidget::item { padding: 10px; }")
        layout.addWidget(self.list_widget, stretch=3)

        # TODO (pendiente de ubicación definitiva): el mockup de esta pantalla
        # no muestra estos botones. Se dejan aquí, discretos, para no perder
        # la función mientras se decide dónde van (¿toolbar? ¿menú contextual?).
        actions_row = QHBoxLayout()
        self.btn_clean = QPushButton(" Limpiar sel.")
        self.btn_clean.clicked.connect(self.on_clean_videos)
        self.btn_clean.setEnabled(False)
        self.btn_clean_all = QPushButton(" Limpiar todos")
        self.btn_clean_all.clicked.connect(self.on_clean_all)
        self.btn_clean_all.setEnabled(False)
        self.btn_cut = QPushButton(" Cortar video")
        self.btn_cut.clicked.connect(self.on_cut_video)
        self.btn_cut.setEnabled(False)
        actions_row.addWidget(self.btn_clean)
        actions_row.addWidget(self.btn_clean_all)
        actions_row.addWidget(self.btn_cut)
        layout.addLayout(actions_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # stretch=1 en vez del alto fijo que tenía antes: sigue siendo
        # más chico que la lista (stretch=3), pero ya no compite con un
        # VideoInfoPanel que ocupaba espacio sin aportar nada aquí.
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        layout.addWidget(self.log_area, stretch=1)

        return panel

    def _build_right_column(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Subir nuevo video")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        # --- Vista previa grande del video cargado/seleccionado ---
        # Bloque dominante de la pantalla (el "azul" de la referencia):
        # tamaño mínimo más grande y stretch=3 en el layout vertical,
        # para que absorba todo el espacio extra por encima de la
        # tarjeta de subida (que se queda con su tamaño natural, sin
        # stretch — el "blanco", más chico y de menor jerarquía visual).
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        self.thumbnail_label.setMinimumSize(420, 320)
        self.thumbnail_label.setObjectName("panel")
        self.thumbnail_label.setText("Selecciona un video de la lista para ver su vista previa")
        self.thumbnail_label.setWordWrap(True)
        layout.addWidget(self.thumbnail_label, stretch=3)

        card = QFrame()
        card.setObjectName("panel")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(10)

        params_label = QLabel("INPUT_PARAMETERS")
        params_label.setObjectName("fieldLabel")
        card_layout.addWidget(params_label)

        source_type_label = QLabel("SOURCE_TYPE")
        source_type_label.setObjectName("fieldLabel")
        card_layout.addWidget(source_type_label)

        toggle_row = QHBoxLayout()
        self.btn_ip_camera = QPushButton("IP CAMERA")
        self.btn_ip_camera.clicked.connect(lambda: self._set_source_type("ip_camera"))
        self.btn_file_upload = QPushButton("FILE UPLOAD")
        self.btn_file_upload.clicked.connect(lambda: self._set_source_type("file_upload"))
        toggle_row.addWidget(self.btn_ip_camera)
        toggle_row.addWidget(self.btn_file_upload)
        card_layout.addLayout(toggle_row)

        # --- Bloque RTSP (visible cuando source_type == "ip_camera") ---
        self.rtsp_label = QLabel("RTSP_URL")
        self.rtsp_label.setObjectName("fieldLabel")
        self.rtsp_input = QLineEdit()
        self.rtsp_input.setPlaceholderText("rtsp://usuario:clave@ip:puerto/canal")
        card_layout.addWidget(self.rtsp_label)
        card_layout.addWidget(self.rtsp_input)

        # --- Bloque subir archivo (visible cuando source_type == "file_upload") ---
        self.btn_load = QPushButton("\U0001F4C1 Haz clic para buscar un archivo")
        self.btn_load.clicked.connect(self.on_load_videos)
        card_layout.addWidget(self.btn_load)

        self.btn_connect = QPushButton("CONNECT STREAM")
        self.btn_connect.setObjectName("primary")
        self.btn_connect.clicked.connect(self._on_connect_clicked)
        card_layout.addWidget(self.btn_connect)

        layout.addWidget(card)

        self._set_source_type("ip_camera")  # estado inicial, igual al mockup
        return panel

    # ------------------------------------------------------- toggle fuente --
    def _set_source_type(self, source_type: str):
        self._source_type = source_type
        is_ip = source_type == "ip_camera"

        self.btn_ip_camera.setObjectName("toggleActive" if is_ip else "toggleInactive")
        self.btn_file_upload.setObjectName("toggleInactive" if is_ip else "toggleActive")
        for btn in (self.btn_ip_camera, self.btn_file_upload):
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self.rtsp_label.setVisible(is_ip)
        self.rtsp_input.setVisible(is_ip)
        self.btn_load.setVisible(not is_ip)
        self.btn_connect.setText("CONNECT STREAM" if is_ip else "SUBIR ARCHIVO")

    def _on_connect_clicked(self):
        if self._source_type == "file_upload":
            self.on_load_videos()
        else:
            # La conexión RTSP en vivo queda fuera de alcance por ahora
            # (no hay pantalla de video en vivo en este proyecto). Se
            # deja anotado en el log para no fingir una función que no existe.
            self._log("Conexión RTSP: no implementada (fuera de alcance).")

    # --------------------------------------------------------- cortar video --
    def on_cut_video(self):
        items = self.list_widget.selectedItems()
        if not items:
            QMessageBox.information(self, "Sin selección", "Selecciona un video de la lista para cortar.")
            return
        filename = items[0].data(Qt.UserRole)
        video_info = self.videos.get(filename)
        if not video_info:
            return

        dialog = CutVideoDialog(video_info, parent=self)
        dialog.range_selected.connect(self._on_cut_range_selected)
        dialog.exec()

    def _on_cut_range_selected(self, start_sec: float, end_sec: float):
        # Solo interfaz por ahora: el recorte real queda pendiente de
        # backend (ver TODO en cut_video_dialog.py).
        self._log(
            f" Rango de recorte elegido: {start_sec:.0f}s a {end_sec:.0f}s "
            f"(recorte real pendiente de backend)."
        )

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

            # Fecha real de carga (no inventada por el widget, viene de afuera)
            video_info.loaded_at = datetime.now().strftime("%Y-%m-%d %H:%M")

            self.videos[video_info.filename] = video_info

            item = QListWidgetItem(
                f"✅ {video_info.filename}   —   {video_info.duration_sec:.1f}s"
            )
            item.setData(Qt.UserRole, video_info.filename)
            self.list_widget.addItem(item)
            self._log(f"Cargado: {video_info.filename} — {video_info.width}x{video_info.height} @ {video_info.fps:.1f}fps")

        self.btn_clean.setEnabled(len(self.videos) > 0)
        self.btn_clean_all.setEnabled(len(self.videos) > 0)

    def _on_selection_changed(self):
        items = self.list_widget.selectedItems()
        self.btn_cut.setEnabled(bool(items))
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

        self.footer.reset_fps()
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
        self.footer.note_frame_progress(current)

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
        tabs.addTab(DashboardTab(), "3. Dashboard de Métricas")
        # Futuras pestañas (cuando se agreguen, Dashboard pasa a ser la 5.a
        # y estas dos ocupan los números 3/4 antes que ella):
        # tabs.addTab(DetectionTab(), "N. Detección y Tracking")
        # tabs.addTab(InteractionTab(), "N. Eventos de Interacción")

        self.setCentralWidget(tabs)