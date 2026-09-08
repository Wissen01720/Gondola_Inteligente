"""
Pestaña de edición de zonas (ROI).

Layout simplificado (esta versión): se quitó `VideoInfoPanel` de esta
pantalla (el header ya muestra el nombre del video activo, así que ese
panel era información repetida sin ninguna acción real). El panel
"Regiones de interés activas" pasó de la derecha a la izquierda, y el
lienzo de dibujo ahora ocupa el resto del ancho disponible — antes
competía por espacio con tres columnas, ahora son solo dos.
"""
import cv2
import numpy as np
from pathlib import Path
from typing import List, Optional, Tuple

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.detection.event_publisher import InProcessPublisher
from app.core.detection.pipeline import DetectionPipeline
from app.core.detection.pipeline_worker import DetectionPipelineWorker
from app.core.detection.pose import PoseEstimator
from app.core.detection.schemas import Zone
from app.core.detection.state_machine import InteractionStateMachine
from app.core.detection.tracker import PersonTracker
from app.core.detection.zone import ZoneManager
from app.core.ingestion.frame_source import VideoFileFrameSource
from app.core.ingestion.video_loader import VideoLoadError, extract_thumbnail, load_video
from app.ui.widgets.footer import FooterBar
from app.ui.widgets.header import HeaderBar
from app.utils.config import LOGS_DIR


def _polygon_area_px(points: List[Tuple[float, float]]) -> float:
    """
    Área de un polígono en píxeles cuadrados (fórmula del "shoelace").
    No hay calibración píxel→metro en el proyecto: este valor es solo
    referencial en px², no representa metros cuadrados reales.
    """
    if len(points) < 3:
        return 0.0
    area = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


class InfoBanner(QFrame):
    """Aviso informativo sobre el lienzo (ej. "Modo de dibujo de ROI's")."""

    def __init__(self, title: str, description: str, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        title_label = QLabel(f"\u24D8  {title}")  # símbolo "ⓘ"
        title_label.setObjectName("sectionTitle")
        layout.addWidget(title_label)

        desc_label = QLabel(description)
        desc_label.setObjectName("mutedText")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)


class ZoneCanvas(QWidget):
    """Lienzo sobre el frame de referencia: cada click agrega un vértice del polígono."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(480, 320)
        self.setStyleSheet("background: #0F0E0A; border: 1px solid #332F22;")
        self._image: Optional[QImage] = None
        self._offset = (0.0, 0.0)
        self._scale = 1.0
        self.points: List[Tuple[float, float]] = []
        self.existing_zone: Optional[Zone] = None  # zona guardada seleccionada (overlay azul)

    # ------------------------------------------------------------- API --
    def set_frame(self, image: QImage) -> None:
        """Fija el frame de referencia (resolución original) y reinicia el dibujo."""
        self._image = image
        self.points = []
        self.existing_zone = None
        self.update()

    def has_frame(self) -> bool:
        return self._image is not None

    def clear_points(self) -> None:
        self.points = []
        self.update()

    def undo_point(self) -> None:
        if self.points:
            self.points.pop()
            self.update()

    # ----------------------------------------------------- geometría --
    def _widget_to_image(self, widget_pos: QPointF) -> Optional[Tuple[float, float]]:
        """Convierte un punto del widget a coordenadas del frame original."""
        if self._image is None or self._scale <= 0:
            return None
        img_x = (widget_pos.x() - self._offset[0]) / self._scale
        img_y = (widget_pos.y() - self._offset[1]) / self._scale
        if img_x < 0 or img_y < 0 or img_x >= self._image.width() or img_y >= self._image.height():
            return None
        return (img_x, img_y)

    def _image_to_widget(self, img_x: float, img_y: float) -> QPointF:
        return QPointF(
            self._offset[0] + img_x * self._scale,
            self._offset[1] + img_y * self._scale,
        )

    # --------------------------------------------------------- eventos --
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._image is not None:
            xy = self._widget_to_image(event.position())
            if xy is not None:
                self.points.append(xy)
                self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0F0E0A"))

        if self._image is None:
            painter.setPen(QColor("#9A9890"))
            painter.drawText(self.rect(), Qt.AlignCenter, "Carga un video para definir zonas")
            return

        # Dibujar frame escalado (KeepAspectRatio, centrado)
        pixmap = QPixmap.fromImage(self._image)
        scaled = pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        offset_x = (self.width() - scaled.width()) // 2
        offset_y = (self.height() - scaled.height()) // 2
        self._offset = (float(offset_x), float(offset_y))
        self._scale = scaled.width() / pixmap.width()
        painter.drawPixmap(offset_x, offset_y, scaled)

        # Overlay: zona ya guardada seleccionada (azul)
        if self.existing_zone is not None and len(self.existing_zone.polygon) >= 3:
            pts = [self._image_to_widget(x, y) for (x, y) in self.existing_zone.polygon]
            painter.setPen(QPen(QColor(0, 128, 255), 2))
            painter.drawPolyline(pts + [pts[0]])
            painter.setBrush(QColor(0, 128, 255))
            painter.setPen(Qt.NoPen)
            for p in pts:
                painter.drawEllipse(p, 3, 3)

        # Polígono en construcción — puntos en amarillo de marca
        pts = [self._image_to_widget(x, y) for (x, y) in self.points]
        if pts:
            painter.setPen(QPen(QColor("#D8C61A"), 2))
            painter.drawPolyline(pts + [pts[0]])
            painter.setBrush(QColor("#D8C61A"))
            painter.setPen(Qt.NoPen)
            for p in pts:
                painter.drawEllipse(p, 4, 4)


class ZoneEditorTab(QWidget):
    """Pestaña 2: Dibujo manual de zonas (ROI) sobre el frame de referencia."""

    def __init__(self):
        super().__init__()
        self.zone_manager = ZoneManager()
        self._current_video_id: Optional[str] = None
        self._current_video_path: Optional[Path] = None
        self._current_video_fps: float = 30.0
        self._debug_worker: Optional[DetectionPipelineWorker] = None
        self._debug_reference_image: Optional[QImage] = None
        self._debug_zones: List[Zone] = []
        self._build_ui()
        self._refresh_zone_list()

    # ---------------------------------------------------------------- UI --
    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        self.header = HeaderBar(source_name="VISION_ZONE_05")
        main_layout.addWidget(self.header)

        # --- Zona central: panel de zonas (izquierda) + lienzo (derecha, más grande) ---
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_zone_panel())
        splitter.addWidget(self._build_canvas_section())
        splitter.setSizes([300, 780])  # el lienzo ahora domina el espacio
        main_layout.addWidget(splitter, stretch=1)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(70)
        main_layout.addWidget(self.log_area)

        self.footer = FooterBar()
        main_layout.addWidget(self.footer)

    def _build_canvas_section(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)

        self.banner = InfoBanner(
            "Modo de dibujo de ROI's",
            "Dibuja o edita cómo están las áreas en donde los clientes "
            "sacan y ponen los productos de las góndolas.",
        )
        layout.addWidget(self.banner)

        self.canvas = ZoneCanvas()
        layout.addWidget(self.canvas, stretch=1)

        # --- Barra de acciones ---
        actions = QHBoxLayout()
        self.btn_load = QPushButton("Cargar video")
        self.btn_load.clicked.connect(self._on_load_video)
        self.btn_undo = QPushButton("Deshacer punto")
        self.btn_undo.clicked.connect(self._on_undo)
        self.btn_clear = QPushButton("Limpiar puntos")
        self.btn_clear.clicked.connect(self._on_clear)
        self.btn_debug = QPushButton("Ver detección (debug)")
        self.btn_debug.clicked.connect(self.on_run_debug)

        actions.addWidget(self.btn_load)
        actions.addWidget(self.btn_undo)
        actions.addWidget(self.btn_clear)
        actions.addWidget(self.btn_debug)
        actions.addStretch()
        layout.addLayout(actions)

        return container

    def _build_zone_panel(self) -> QWidget:
        """Panel izquierdo: "Regiones de interés activas" + formulario de guardado."""
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)

        title = QLabel("Regiones de interés activas")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self.zone_list = QListWidget()
        self.zone_list.itemSelectionChanged.connect(self._on_zone_selected)
        layout.addWidget(self.zone_list, stretch=1)

        # --- Formulario para guardar la zona en construcción ---
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Nombre:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ej: Góndola A1, Pasillo 2, ...")
        name_row.addWidget(self.name_input, stretch=1)
        layout.addLayout(name_row)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Tipo:"))
        self.type_combo = QComboBox()
        # Los únicos dos valores que el esquema `Zone.zone_type` acepta hoy.
        self.type_combo.addItem("Góndola / producto (dwell time)", userData="product")
        self.type_combo.addItem("Personal (excluida de métricas)", userData="staff")
        type_row.addWidget(self.type_combo, stretch=1)
        layout.addLayout(type_row)

        hint = QLabel(
            "Haz click sobre el frame para agregar vértices. Mínimo 3 puntos."
        )
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons_row = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self._on_clear)

        self.btn_save = QPushButton("Guardar zona")
        self.btn_save.setObjectName("primary")
        self.btn_save.clicked.connect(self._on_save)

        buttons_row.addWidget(self.btn_cancel)
        buttons_row.addWidget(self.btn_save)
        layout.addLayout(buttons_row)

        return panel

    # --------------------------------------------------------- acciones --
    def _on_load_video(self):
        """Carga un video y extrae el frame de referencia (10% de su duración)."""
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar video para frame de referencia", str(Path.home()), "Videos (*.mp4 *.avi *.mov *.mkv *.wmv)"
        )
        if not path_str:
            return

        try:
            video_info = load_video(Path(path_str))
        except VideoLoadError as exc:
            self._log(f"❌ {exc}")
            return

        thumb_path = LOGS_DIR / f"{Path(path_str).stem}_ref.jpg"
        try:
            extract_thumbnail(video_info, thumb_path)
            image = QImage(str(thumb_path))
            if image.isNull():
                raise VideoLoadError(f"No se pudo leer la miniatura: {thumb_path}")
            self.canvas.set_frame(image)
            self._current_video_id = video_info.path.stem
            self._current_video_path = video_info.path
            self._current_video_fps = video_info.fps or 30.0
            self.header.set_source_name(video_info.filename)
            self._refresh_zone_list()
            self._log(f"✅ Frame de referencia cargado: {video_info.filename} "
                      f"({video_info.width}x{video_info.height}) — escala de dibujo lista.")
        except VideoLoadError as exc:
            self._log(f"❌ {exc}")

    def _on_undo(self):
        self.canvas.undo_point()
        self._refresh_zone_list()

    def _on_clear(self):
        self.canvas.clear_points()
        self.name_input.clear()
        self._refresh_zone_list()

    # ------------------------------------------------- debug de detección --
    def on_run_debug(self):
        """
        Corre el pipeline sobre el mismo video que está cargado en el
        lienzo, en un QThread (DetectionPipelineWorker) — no un proceso
        aparte. El frame anotado (cajas + zonas) se muestra directamente
        sobre el lienzo del ROI, reemplazando temporalmente el frame de
        referencia mientras corre.
        """
        if self._current_video_path is None:
            QMessageBox.warning(self, "Sin video", "Carga primero un video con 'Cargar video'.")
            return
        if self.canvas.points:
            QMessageBox.warning(
                self, "Dibujo en curso",
                "Guarda o descarta ('Limpiar puntos') el polígono actual antes de correr el debug.",
            )
            return
        if self._debug_worker is not None and self._debug_worker.isRunning():
            QMessageBox.warning(self, "En curso", "Ya hay un debug corriendo, espera a que termine.")
            return

        self._debug_zones = self.zone_manager.load_zones(self._current_video_id)
        if not self._debug_zones:
            self._log(
                f"⚠️ No hay zonas guardadas para '{self._current_video_id}' — se va a "
                "mostrar el video sin zonas dibujadas."
            )

        try:
            source = VideoFileFrameSource(self._current_video_path)
        except (FileNotFoundError, IOError) as exc:
            self._log(f"❌ No se pudo abrir el video: {exc}")
            return

        tracker = PersonTracker()
        pose_estimator = PoseEstimator()
        state_machine = InteractionStateMachine(fps=self._current_video_fps)
        publisher = InProcessPublisher()
        pipeline = DetectionPipeline(tracker, pose_estimator, self.zone_manager, state_machine, publisher)

        # ~10 actualizaciones de imagen por segundo, sin importar el fps
        # real del video — evita saturar la cola de eventos de Qt.
        frame_every_n = max(1, round(self._current_video_fps / 10))

        self._debug_reference_image = self.canvas._image

        self._debug_worker = DetectionPipelineWorker(pipeline, source, frame_every_n=frame_every_n)
        self._debug_worker.frame_processed.connect(self._on_debug_frame)
        self._debug_worker.pipeline_finished.connect(self._on_debug_finished)
        self._debug_worker.pipeline_failed.connect(self._on_debug_failed)

        self.btn_debug.setEnabled(False)
        self.btn_load.setEnabled(False)
        self._log(f"🔎 Corriendo debug de detección sobre {self._current_video_path.name} (en el lienzo)...")
        self._debug_worker.start()

    def _on_debug_frame(self, frame, call_count, tracked_people, pose_results):
        annotated = frame.copy()
        for person in tracked_people:
            x1, y1, x2, y2 = map(int, person.bbox)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (26, 198, 216), 3)  # BGR de #D8C61A
        for zone in self._debug_zones:
            pts = np.array(zone.polygon, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(annotated, [pts], isClosed=True, color=(70, 200, 70), thickness=2)

        rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()
        self.canvas.set_frame(qimg)

    def _on_debug_finished(self, total_frames: int):
        self.btn_debug.setEnabled(True)
        self.btn_load.setEnabled(True)
        if self._debug_reference_image is not None:
            self.canvas.set_frame(self._debug_reference_image)
            self._refresh_zone_list()
        self._log(f"✅ Debug terminado — {total_frames} frames procesados.")

    def _on_debug_failed(self, message: str):
        self.btn_debug.setEnabled(True)
        self.btn_load.setEnabled(True)
        if self._debug_reference_image is not None:
            self.canvas.set_frame(self._debug_reference_image)
            self._refresh_zone_list()
        self._log(f"❌ Falló el debug: {message}")

    def _on_save(self):
        """Guarda la zona dibujada con el esquema `Zone` vía ZoneManager."""
        if self.canvas._image is None or self._current_video_id is None:
            QMessageBox.warning(self, "Sin frame", "Carga primero un video con el frame de referencia.")
            return
        if len(self.canvas.points) < 3:
            QMessageBox.warning(self, "Polígono incompleto", "Se necesitan al menos 3 puntos.")
            return
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Sin nombre", "Escribe un nombre para la zona.")
            return

        zone_id = self._next_zone_id()
        polygon = [(round(x, 2), round(y, 2)) for (x, y) in self.canvas.points]
        zone_type = self.type_combo.currentData()
        zone = Zone(zone_id=zone_id, video_id=self._current_video_id, name=name, polygon=polygon, zone_type=zone_type)
        self.zone_manager.save_zone(zone)
        self._log(f"✅ Zona guardada: {zone_id} — {name} ({len(polygon)} vértices, tipo={zone_type}) [{self._current_video_id}]")

        self.name_input.clear()
        self.canvas.clear_points()
        self._refresh_zone_list()

    def _next_zone_id(self) -> str:
        """Genera el siguiente zone_id libre (zone_1, zone_2, ...) para el video actual, sin pisar los existentes."""
        existing = set()
        video_dir = self.zone_manager.storage_path / self._current_video_id
        if video_dir.exists():
            for f in video_dir.glob("*.json"):
                existing.add(f.stem)
        n = 1
        while f"zone_{n}" in existing:
            n += 1
        return f"zone_{n}"

    # ----------------------------------------------------------- helpers --
    def _refresh_zone_list(self):
        """
        Repuebla la lista de "Regiones de interés activas".

        Muestra primero (si existen) los puntos que se están dibujando
        ahora mismo, sin guardar todavía, y luego las zonas ya
        guardadas para el video actual.
        """
        self.zone_list.clear()
        self._zones = {}

        if self.canvas.points:
            self._add_zone_row(
                name=self.name_input.text().strip() or "(sin nombre aún)",
                nodes=len(self.canvas.points),
                area_px=0.0,
                zone_type="—",
                status="Dibujando",
                zone_id=None,
            )

        if self._current_video_id is None:
            return

        self._zones = {z.zone_id: z for z in self.zone_manager.load_zones(self._current_video_id)}
        for zone_id, zone in self._zones.items():
            self._add_zone_row(
                name=zone.name,
                nodes=len(zone.polygon),
                area_px=_polygon_area_px(zone.polygon),
                zone_type=zone.zone_type,
                status="Válida",
                zone_id=zone_id,
            )

    def _add_zone_row(self, name: str, nodes: int, area_px: float, zone_type: str, status: str, zone_id: Optional[str]):
        """Agrega una fila con estilo de tarjeta al QListWidget de zonas."""
        row = QWidget()
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(6, 4, 6, 4)
        row_layout.setSpacing(1)

        name_label = QLabel(name)
        name_label.setObjectName("sectionTitle")
        row_layout.addWidget(name_label)

        area_text = f"{area_px:,.0f} px²" if area_px > 0 else "--"
        detail_label = QLabel(
            f"Nodos: {nodes}   Área: {area_text}   Tipo: {zone_type}   Estado: {status}"
        )
        detail_label.setObjectName("mutedText")
        detail_label.setWordWrap(True)
        row_layout.addWidget(detail_label)

        item = QListWidgetItem()
        item.setSizeHint(row.sizeHint())
        item.setData(Qt.UserRole, zone_id)
        self.zone_list.addItem(item)
        self.zone_list.setItemWidget(item, row)

    def _on_zone_selected(self):
        items = self.zone_list.selectedItems()
        if not items:
            return
        zone_id = items[0].data(Qt.UserRole)
        if zone_id is None:
            return  # es la fila "(Drawing)", no una zona guardada
        zone = self._zones.get(zone_id)
        if zone and self.canvas.has_frame():
            self.canvas.existing_zone = zone
            self.canvas.update()

    def _log(self, message: str):
        self.log_area.append(message)