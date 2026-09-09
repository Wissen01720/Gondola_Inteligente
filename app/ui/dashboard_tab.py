"""
Pestaña 5: Dashboard de Métricas (Team 4).

A diferencia del resto de la UI (que opera sobre archivos/estado en
memoria), este tab lee directamente de `EventStore` (SQLite,
`data/scapder_events.db`) — el mismo almacén al que el pipeline de
detección publica en producción vía `InProcessPublisher`. No hay datos
mockeados en el widget: si la sesión ya tiene eventos reales, se grafican
esos; si está vacía (el pipeline de las pestañas 3/4 aún no corrió),
se ofrece sembrar una sesión de demostración explícitamente marcada como
tal (ver `app/core/backend/demo_seed.py`), nunca de forma automática o
silenciosa.
"""
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import QPointF, Qt, QTimer, QRectF
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.backend.demo_seed import FRAME_SIZE, has_data, seed_demo_session
from app.core.backend.event_store import EventStore
from app.core.backend.heatmap import build_density_grid
from app.core.detection.schemas import Zone
from app.core.detection.zone import ZoneManager
from app.ui.theme import Colors
from app.ui.widgets.header import HeaderBar
from app.utils import config

TAKEN_COLOR = Colors.ACCENT
RETURNED_COLOR = Colors.INFO_BLUE
EMPLOYEE_COLOR = Colors.WARNING

REFRESH_INTERVAL_MS = 3000


# ============================================================ widgets base --
class Card(QFrame):
    """Tarjeta contenedora estándar del dashboard (título + contenido)."""

    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        head = QVBoxLayout()
        head.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        head.addWidget(title_label)
        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setObjectName("mutedText")
            head.addWidget(sub_label)
        layout.addLayout(head)

        self.body = QVBoxLayout()
        self.body.setSpacing(6)
        layout.addLayout(self.body, stretch=1)


class KpiCard(QFrame):
    """Tarjeta compacta: etiqueta + valor grande + nota."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        self.label = QLabel(label)
        self.label.setObjectName("fieldLabel")
        layout.addWidget(self.label)

        self.value_label = QLabel("—")
        self.value_label.setStyleSheet(f"color: {Colors.TEXT_PRIMARY}; font-size: 20pt; font-weight: 700;")
        layout.addWidget(self.value_label)

        self.note_label = QLabel("")
        self.note_label.setObjectName("mutedText")
        layout.addWidget(self.note_label)

    def set_value(self, value: str, note: str = "", note_color: str | None = None):
        self.value_label.setText(value)
        self.note_label.setText(note)
        color = note_color or Colors.TEXT_SECONDARY
        self.note_label.setStyleSheet(f"color: {color}; font-size: 9pt;")


class EmptyState(QLabel):
    """Aviso centrado para gráficos sin datos (evita canvases vacíos mudos)."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
        self.setObjectName("mutedText")
        self.setMinimumHeight(80)


# ============================================================ gráficos ------
class ZoneBarChart(QWidget):
    """Barras horizontales agrupadas: `taken` vs `returned` por zona."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict] = []
        self.setMinimumHeight(140)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

    def set_data(self, rows: list[dict]):
        self._rows = rows
        row_h = 46
        self.setMinimumHeight(max(140, len(rows) * row_h + 20))
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if not self._rows:
            painter.end()
            return

        w = self.width()
        row_h = 46
        max_total = max((r["taken"] + r["returned"] for r in self._rows), default=1) or 1
        label_w = 170
        bar_x0 = label_w
        bar_w_max = w - bar_x0 - 60

        font_label = QFont("Segoe UI", 9)
        font_mono = QFont("Consolas", 8)

        for i, row in enumerate(self._rows):
            y = i * row_h
            name = row.get("name", row["zone_id"])
            total = row["taken"] + row["returned"]

            painter.setFont(font_label)
            painter.setPen(QColor(Colors.TEXT_PRIMARY))
            painter.drawText(QRectF(0, y + 4, label_w - 10, 18), Qt.AlignLeft | Qt.AlignVCenter, name)
            painter.setFont(font_mono)
            painter.setPen(QColor(Colors.TEXT_MUTED))
            painter.drawText(
                QRectF(0, y + 22, label_w - 10, 14), Qt.AlignLeft | Qt.AlignVCenter,
                f"{row['zone_id']} · {total} eventos",
            )

            track_rect = QRectF(bar_x0, y + 8, bar_w_max, 18)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(Colors.BG_INPUT))
            painter.drawRoundedRect(track_rect, 4, 4)

            taken_w = bar_w_max * (row["taken"] / max_total)
            returned_w = bar_w_max * (row["returned"] / max_total)

            painter.setBrush(QColor(TAKEN_COLOR))
            painter.drawRoundedRect(QRectF(bar_x0, y + 8, taken_w, 18), 4, 4)
            painter.setBrush(QColor(RETURNED_COLOR))
            painter.drawRoundedRect(QRectF(bar_x0 + taken_w + 2, y + 8, returned_w, 18), 4, 4)

            painter.setFont(font_mono)
            painter.setPen(QColor(Colors.TEXT_SECONDARY))
            dwell_text = f"{row['avg_dwell_sec']:.1f}s dwell"
            painter.drawText(
                QRectF(bar_x0 + bar_w_max + 6, y + 8, 54, 18), Qt.AlignLeft | Qt.AlignVCenter, dwell_text
            )

        painter.end()


class TimelineChart(QWidget):
    """Línea de `taken`/`returned` por bucket de tiempo, con relleno bajo la curva."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bins: list[dict] = []
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

    def set_data(self, bins: list[dict]):
        self._bins = bins
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if len(self._bins) < 2:
            painter.end()
            return

        pad_l, pad_r, pad_t, pad_b = 34, 10, 10, 20
        w, h = self.width(), self.height()
        plot_w = w - pad_l - pad_r
        plot_h = h - pad_t - pad_b
        n = len(self._bins)
        max_v = max((b["taken"] + b["returned"] for b in self._bins), default=1) or 1
        x_step = plot_w / (n - 1)

        def xy(i, v):
            x = pad_l + i * x_step
            y = pad_t + plot_h - (v / max_v) * plot_h
            return x, y

        # grid
        painter.setPen(QPen(QColor(Colors.BORDER_SOFT), 1))
        for f in (0, 0.5, 1.0):
            y = pad_t + plot_h * (1 - f)
            painter.drawLine(int(pad_l), int(y), int(w - pad_r), int(y))
            painter.setPen(QColor(Colors.TEXT_MUTED))
            painter.setFont(QFont("Consolas", 7))
            painter.drawText(0, int(y) + 3, pad_l - 6, 10, Qt.AlignRight, str(int(max_v * f)))
            painter.setPen(QPen(QColor(Colors.BORDER_SOFT), 1))

        def draw_series(key, color, dashed=False):
            pen = QPen(QColor(color), 2)
            if dashed:
                pen.setStyle(Qt.DashLine)
            painter.setPen(pen)
            points = [xy(i, b[key]) for i, b in enumerate(self._bins)]
            for j in range(len(points) - 1):
                x1, y1 = points[j]
                x2, y2 = points[j + 1]
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        # área bajo "taken"
        fill_points = [xy(i, b["taken"]) for i, b in enumerate(self._bins)]
        fill_color = QColor(TAKEN_COLOR)
        fill_color.setAlpha(40)
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill_color)
        from PySide6.QtGui import QPolygonF
        from PySide6.QtCore import QPointF
        poly = QPolygonF([QPointF(*p) for p in fill_points])
        poly.append(QPointF(*xy(n - 1, 0)))
        poly.append(QPointF(*xy(0, 0)))
        painter.drawPolygon(poly)

        draw_series("taken", TAKEN_COLOR)
        draw_series("returned", RETURNED_COLOR, dashed=True)

        painter.end()


class HeatmapWidget(QWidget):
    """
    Mapa de calor de circulación sobre el layout real de la góndola.

    Construido con `build_density_grid` (app/core/backend/heatmap.py) a
    partir de los `PositionSample.foot_position` almacenados — los mismos
    "puntos de pie" que publica el pipeline por cada frame y cada persona
    trackeada. Sobre esa cuadrícula se dibuja el contorno de cada zona
    (sólido = producto, punteado = personal) en su posición real.
    """

    GRID_SIZE = (64, 36)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._samples = []
        self._zones: list[Zone] = []
        self._frame_size = FRAME_SIZE
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

    def set_data(self, samples, zones: list[Zone], frame_size: tuple[int, int] = FRAME_SIZE):
        self._samples = samples
        self._zones = zones
        self._frame_size = frame_size
        self.update()

    def _draw_area_rect(self) -> QRectF:
        """ROI dibujable dentro del widget, respetando el aspecto del frame."""
        frame_w, frame_h = self._frame_size
        aspect = frame_w / frame_h
        w, h = self.width(), self.height()
        if w / h > aspect:
            draw_h = h
            draw_w = h * aspect
        else:
            draw_w = w
            draw_h = w / aspect
        return QRectF((w - draw_w) / 2, (h - draw_h) / 2, draw_w, draw_h)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        draw_rect = self._draw_area_rect()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(Colors.BG_INPUT))
        painter.drawRoundedRect(draw_rect, 6, 6)

        if self._samples:
            cols, rows = self.GRID_SIZE
            grid = build_density_grid(self._samples, self._frame_size, grid_size=self.GRID_SIZE, sigma=1.2)
            peak = float(grid.max()) or 1.0
            normalized = np.clip((grid / peak) * 255, 0, 255).astype(np.uint8)
            colored_bgr = cv2.applyColorMap(normalized, cv2.COLORMAP_INFERNO)
            colored_rgb = cv2.cvtColor(colored_bgr, cv2.COLOR_BGR2RGB)
            # Celdas casi vacías se dejan transparentes para no pintar todo
            # el frame de "azul oscuro" cuando en realidad no hay muestras ahí.
            alpha = np.where(normalized > 6, 235, 0).astype(np.uint8)
            rgba = np.ascontiguousarray(np.dstack([colored_rgb, alpha]))
            image = QImage(rgba.data, cols, rows, rgba.strides[0], QImage.Format_RGBA8888)
            painter.drawImage(draw_rect, image)

        frame_w, frame_h = self._frame_size
        sx, sy = draw_rect.width() / frame_w, draw_rect.height() / frame_h

        def to_widget(point: tuple[float, float]) -> QPointF:
            return QPointF(draw_rect.left() + point[0] * sx, draw_rect.top() + point[1] * sy)

        for zone in self._zones:
            is_staff = zone.zone_type == "staff"
            pen = QPen(QColor(Colors.INFO_BLUE if not is_staff else Colors.WARNING), 2)
            if is_staff:
                pen.setStyle(Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPolygon(QPolygonF([to_widget(p) for p in zone.polygon]))

            centroid = to_widget((
                sum(p[0] for p in zone.polygon) / len(zone.polygon),
                sum(p[1] for p in zone.polygon) / len(zone.polygon),
            ))
            painter.setFont(QFont("Consolas", 7))
            painter.setPen(QColor(Colors.TEXT_PRIMARY))
            painter.drawText(centroid, zone.name)

        painter.setPen(QPen(QColor(Colors.BORDER), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(draw_rect, 6, 6)

        painter.end()


# ============================================================ tab principal --
class DashboardTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.store = EventStore()
        self.zone_manager = ZoneManager()
        self._zone_names: dict[str, str] = {}

        self._build_ui()
        self._populate_sessions()
        self.refresh()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(REFRESH_INTERVAL_MS)

    # -------------------------------------------------------------- UI --
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.header = HeaderBar("DASHBOARD_METRICAS")
        outer.addWidget(self.header)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(12, 10, 12, 0)
        toolbar.addWidget(QLabel("Sesión (video_id):"))
        self.session_combo = QComboBox()
        self.session_combo.setMinimumWidth(260)
        self.session_combo.currentIndexChanged.connect(self._on_session_changed)
        toolbar.addWidget(self.session_combo)
        toolbar.addStretch()

        self.status_label = QLabel("")
        self.status_label.setObjectName("mutedText")
        toolbar.addWidget(self.status_label)

        self.btn_seed = QPushButton("Cargar sesión de demostración")
        self.btn_seed.setToolTip(
            "Genera eventos de ejemplo (marcados como demo) para esta sesión "
            "mientras el pipeline de detección no haya publicado eventos reales."
        )
        self.btn_seed.clicked.connect(self._on_seed_demo)
        toolbar.addWidget(self.btn_seed)

        self.btn_refresh = QPushButton("Actualizar")
        self.btn_refresh.setObjectName("primary")
        self.btn_refresh.clicked.connect(self.refresh)
        toolbar.addWidget(self.btn_refresh)

        outer.addLayout(toolbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(12)

        # --- KPI row ---
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(10)
        self.kpi_total = KpiCard("INTERACCIONES TOTALES")
        self.kpi_take_rate = KpiCard("TASA DE TOMA NETA")
        self.kpi_dwell = KpiCard("DWELL PROMEDIO")
        self.kpi_employee = KpiCard("PERSONAL DETECTADO (STAFF)")
        self.kpi_zones = KpiCard("ZONAS ACTIVAS")
        for kpi in (self.kpi_total, self.kpi_take_rate, self.kpi_dwell, self.kpi_employee, self.kpi_zones):
            kpi_row.addWidget(kpi)
        content_layout.addLayout(kpi_row)

        # --- grid principal: gráficos (izq, ancho) + laterales (der) ---
        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 1)

        timeline_card = Card("Interacciones por bucket de tiempo", "Tomado (línea sólida) vs. devuelto (línea punteada)")
        self.timeline_chart = TimelineChart()
        self.timeline_empty = EmptyState("Sin eventos aún. Corre el pipeline o carga la sesión de demostración.")
        timeline_card.body.addWidget(self.timeline_chart)
        timeline_card.body.addWidget(self.timeline_empty)
        grid.addWidget(timeline_card, 0, 0)

        zones_card = Card("Desempeño por zona de producto", "InteractionEvent.action agrupado por zone_id")
        self.zone_chart = ZoneBarChart()
        self.zone_empty = EmptyState("Sin eventos por zona todavía.")
        zones_card.body.addWidget(self.zone_chart)
        zones_card.body.addWidget(self.zone_empty)
        grid.addWidget(zones_card, 1, 0)

        recent_card = Card("Eventos recientes", "event_store.db · tabla events")
        self.events_table = QTableWidget(0, 4)
        self.events_table.setHorizontalHeaderLabels(["Track", "Zona", "Acción", "t (s)"])
        self.events_table.verticalHeader().setVisible(False)
        self.events_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.events_table.setSelectionMode(QTableWidget.NoSelection)
        self.events_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.events_table.setMinimumHeight(240)
        recent_card.body.addWidget(self.events_table)
        grid.addWidget(recent_card, 2, 0)

        heatmap_card = Card("Mapa de calor de circulación", "PositionSample.foot_position sobre el ROI real")
        self.heatmap = HeatmapWidget()
        self.heatmap_empty = EmptyState("Sin muestras de posición aún (PositionSample vacío).")
        heatmap_card.body.addWidget(self.heatmap)
        heatmap_card.body.addWidget(self.heatmap_empty)
        grid.addWidget(heatmap_card, 0, 1)

        perf_card = Card("Zonas con más movimiento", "Ranking por eventos totales")
        self.ranking_label = QLabel("")
        self.ranking_label.setWordWrap(True)
        perf_card.body.addWidget(self.ranking_label)
        grid.addWidget(perf_card, 1, 1)

        legend_card = Card("Leyenda")
        legend_layout = QVBoxLayout()
        legend_layout.addWidget(self._legend_row(TAKEN_COLOR, "Tomado (taken)"))
        legend_layout.addWidget(self._legend_row(RETURNED_COLOR, "Devuelto (returned)"))
        legend_layout.addWidget(self._legend_row(Colors.INFO_BLUE, "Zona de producto (ROI)"))
        legend_layout.addWidget(self._legend_row(EMPLOYEE_COLOR, "Zona de personal (ROI)"))
        legend_card.body.addLayout(legend_layout)
        grid.addWidget(legend_card, 2, 1)

        content_layout.addLayout(grid)
        content_layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

    @staticmethod
    def _legend_row(color: str, text: str) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        dot = QLabel()
        dot.setFixedSize(10, 10)
        dot.setStyleSheet(f"background-color:{color}; border-radius:5px;")
        layout.addWidget(dot)
        label = QLabel(text)
        label.setObjectName("mutedText")
        layout.addWidget(label)
        layout.addStretch()
        return row

    # --------------------------------------------------------- sesiones --
    def _populate_sessions(self):
        base = Path(config.ZONES_STORAGE_PATH)
        video_ids = sorted(p.name for p in base.iterdir() if p.is_dir()) if base.exists() else []
        self.session_combo.blockSignals(True)
        self.session_combo.clear()
        self.session_combo.addItems(video_ids or ["(sin zonas guardadas)"])
        self.session_combo.blockSignals(False)
        self._load_zone_names()

    def _on_session_changed(self, _index: int):
        self._load_zone_names()
        self.refresh()

    def _load_zone_names(self):
        video_id = self.session_combo.currentText()
        zones = self.zone_manager.load_zones(video_id) if video_id else []
        self._zone_names = {z.zone_id: z.name for z in zones}
        self._current_zones = zones

    # ----------------------------------------------------------- acciones --
    def _on_seed_demo(self):
        zones = getattr(self, "_current_zones", [])
        if not zones:
            self.status_label.setText("No hay zonas guardadas para esta sesión: crea zonas en la pestaña 2 primero.")
            return
        inserted = seed_demo_session(self.store, zones)
        self.status_label.setText(f"Sesión de demostración cargada ({inserted} eventos sintéticos).")
        self.refresh()

    # ------------------------------------------------------------ refresco --
    def refresh(self):
        summary = self.store.get_summary()
        zone_rows = self.store.get_zone_breakdown()
        timeline = self.store.get_timeline(bucket_sec=30.0)
        recent = self.store.get_recent_events(limit=15)
        position_samples = self.store.get_position_samples()

        is_demo = not has_data(self.store)
        self.btn_seed.setEnabled(is_demo)
        if is_demo and not self.status_label.text():
            self.status_label.setText("Sin eventos reales todavía — el pipeline de detección aún no publicó nada.")

        # KPIs
        self.kpi_total.set_value(str(summary["total_events"]))
        self.kpi_take_rate.set_value(
            f"{summary['take_rate']*100:.1f}%",
            f"{summary['taken']} tomados / {summary['returned']} devueltos",
        )
        self.kpi_dwell.set_value(f"{summary['avg_dwell_sec']:.1f}s")
        self.kpi_employee.set_value(
            f"{summary['employee_share']*100:.1f}%",
            f"{summary['employee_events']} de {summary['total_events']} eventos",
        )
        self.kpi_zones.set_value(str(summary["active_zones"]))

        # Zone chart
        for row in zone_rows:
            row["name"] = self._zone_names.get(row["zone_id"], row["zone_id"])
        self.zone_chart.set_data(zone_rows)
        self.zone_chart.setVisible(bool(zone_rows))
        self.zone_empty.setVisible(not zone_rows)

        # Timeline
        self.timeline_chart.set_data(timeline)
        self.timeline_chart.setVisible(len(timeline) >= 2)
        self.timeline_empty.setVisible(len(timeline) < 2)

        # Heatmap de circulación (PositionSample -> build_density_grid)
        zones = getattr(self, "_current_zones", [])
        self.heatmap.set_data(position_samples, zones)
        self.heatmap.setVisible(bool(position_samples))
        self.heatmap_empty.setVisible(not position_samples)

        # Ranking
        ranked = sorted(zone_rows, key=lambda r: r["taken"] + r["returned"], reverse=True)
        if ranked:
            lines = [
                f"{i+1}. {r['name']} — {r['taken']+r['returned']} eventos ({r['avg_dwell_sec']:.1f}s dwell)"
                for i, r in enumerate(ranked[:5])
            ]
            self.ranking_label.setText("\n".join(lines))
        else:
            self.ranking_label.setText("Sin datos todavía.")

        # Tabla de eventos recientes
        self.events_table.setRowCount(len(recent))
        for i, ev in enumerate(recent):
            zone_name = self._zone_names.get(ev["zone_id"], ev["zone_id"])
            action_item = QTableWidgetItem("● Tomado" if ev["action"] == "taken" else "● Devuelto")
            action_item.setForeground(QColor(TAKEN_COLOR if ev["action"] == "taken" else RETURNED_COLOR))
            self.events_table.setItem(i, 0, QTableWidgetItem(f"#{ev['track_id']}"))
            self.events_table.setItem(i, 1, QTableWidgetItem(zone_name))
            self.events_table.setItem(i, 2, action_item)
            self.events_table.setItem(i, 3, QTableWidgetItem(f"{ev['timestamp']:.1f}"))
