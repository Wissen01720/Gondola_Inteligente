"""
Pestaña de edición de zonas (ROI) — Team 4.

Permite dibujar polígonos de zona con clicks sobre un frame de referencia
(extraído con `extract_thumbnail` del Módulo 1, a resolución completa),
nombrarlos y guardarlos con el esquema `Zone` existente vía `ZoneManager`
(`data/zones/*.json` — no se inventa un formato nuevo).

Los vértices se guardan en coordenadas del frame ORIGINAL (no del lienzo
escalado), así el pipeline puede usarlos tal cual.
"""
from pathlib import Path
from typing import List, Optional, Tuple

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
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

from app.core.detection.schemas import Zone
from app.core.detection.zone import ZoneManager
from app.core.ingestion.video_loader import VideoLoadError, extract_thumbnail, load_video
from app.utils.config import LOGS_DIR


class ZoneCanvas(QWidget):
    """Lienzo sobre el frame de referencia: cada click agrega un vértice del polígono."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(480, 320)
        self.setStyleSheet("background: #1e1e1e; border: 1px solid #444;")
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
        painter.fillRect(self.rect(), QColor("#1e1e1e"))

        if self._image is None:
            painter.setPen(QColor("#999"))
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

        # Polígono en construcción (verde)
        pts = [self._image_to_widget(x, y) for (x, y) in self.points]
        if pts:
            painter.setPen(QPen(QColor(0, 255, 0), 2))
            painter.drawPolyline(pts + [pts[0]])
            painter.setBrush(QColor(255, 0, 0))
            painter.setPen(Qt.NoPen)
            for p in pts:
                painter.drawEllipse(p, 4, 4)


class ZoneEditorTab(QWidget):
    """Pestaña 2: Dibujo manual de zonas (ROI) sobre el frame de referencia."""

    def __init__(self):
        super().__init__()
        self.zone_manager = ZoneManager()
        self._build_ui()
        self._refresh_zone_list()

    # ---------------------------------------------------------------- UI --
    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        # --- Barra de acciones ---
        actions = QHBoxLayout()
        self.btn_load = QPushButton("🎞️ Cargar video (frame de referencia)")
        self.btn_load.clicked.connect(self._on_load_video)
        self.btn_undo = QPushButton("↩️ Deshacer punto")
        self.btn_undo.clicked.connect(self._on_undo)
        self.btn_clear = QPushButton("🧹 Limpiar puntos")
        self.btn_clear.clicked.connect(self._on_clear)
        self.btn_save = QPushButton("💾 Guardar zona")
        self.btn_save.clicked.connect(self._on_save)

        actions.addWidget(self.btn_load)
        actions.addWidget(self.btn_undo)
        actions.addWidget(self.btn_clear)
        actions.addStretch()
        main_layout.addLayout(actions)

        # --- Zona central: lienzo + lista de zonas existentes ---
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_canvas_section())

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("Zonas existentes (data/zones/):"))
        self.zone_list = QListWidget()
        self.zone_list.itemSelectionChanged.connect(self._on_zone_selected)
        right_layout.addWidget(self.zone_list, stretch=1)
        splitter.addWidget(right)

        splitter.setSizes([560, 260])
        main_layout.addWidget(splitter, stretch=1)

        # --- Nombre nuevo + log ---
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Nombre de la zona:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ej: Góndola A1, Pasillo 2, ...")
        name_row.addWidget(self.name_input, stretch=1)
        main_layout.addLayout(name_row)

        hint = QLabel("Haz click sobre el frame para agregar vértices. Mínimo 3 puntos. "
                      "Los puntos se guardan en coordenadas del frame original.")
        main_layout.addWidget(hint)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(80)
        main_layout.addWidget(self.log_area)

    def _build_canvas_section(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        self.canvas = ZoneCanvas()
        layout.addWidget(self.canvas)
        return container

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
            self._log(f"✅ Frame de referencia cargado: {video_info.filename} "
                      f"({video_info.width}x{video_info.height}) — escala de dibujo lista.")
        except VideoLoadError as exc:
            self._log(f"❌ {exc}")

    def _on_undo(self):
        self.canvas.undo_point()

    def _on_clear(self):
        self.canvas.clear_points()

    def _on_save(self):
        """Guarda la zona dibujada con el esquema `Zone` vía ZoneManager."""
        if self.canvas._image is None:
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
        zone = Zone(zone_id=zone_id, name=name, polygon=polygon)
        self.zone_manager.save_zone(zone)
        self._log(f"✅ Zona guardada: {zone_id} — {name} ({len(polygon)} vértices)")

        self.name_input.clear()
        self.canvas.clear_points()
        self._refresh_zone_list()

    def _next_zone_id(self) -> str:
        """Genera el siguiente zone_id libre (zone_1, zone_2, ...) sin pisar los existentes."""
        existing = set()
        for f in self.zone_manager.storage_path.glob("*.json"):
            existing.add(f.stem)
        n = 1
        while f"zone_{n}" in existing:
            n += 1
        return f"zone_{n}"

    # ----------------------------------------------------------- helpers --
    def _refresh_zone_list(self):
        self.zone_list.clear()
        self._zones = {z.zone_id: z for z in self.zone_manager.load_zones()}
        for zone_id, zone in self._zones.items():
            item = QListWidgetItem(f"{zone_id} — {zone.name} ({len(zone.polygon)} pts)")
            item.setData(Qt.UserRole, zone_id)
            self.zone_list.addItem(item)

    def _on_zone_selected(self):
        items = self.zone_list.selectedItems()
        if not items:
            return
        zone = self._zones.get(items[0].data(Qt.UserRole))
        if zone and self.canvas.has_frame():
            self.canvas.existing_zone = zone
            self.canvas.update()

    def _log(self, message: str):
        self.log_area.append(message)