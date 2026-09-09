from PySide6.QtCore import Qt, QPointF, QRectF, QSize, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton


def _create_gear_icon(size: int = 18, color: str = "#F2F0E6") -> QIcon:
    """
    Dibuja un ícono de engranaje como gráfico vectorial (QPainter), en vez
    de depender de un glifo de emoji (⚙) que no todas las fuentes/sistemas
    renderizan igual — el bug documentado de que se veía como "|" en
    Windows era justamente por depender de la fuente del sistema.
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))

    center = size / 2
    outer_r = size * 0.40
    inner_r = size * 0.24
    tooth_w = size * 0.16
    tooth_h = size * 0.16

    # Cuerpo circular del engranaje
    painter.drawEllipse(QPointF(center, center), outer_r, outer_r)

    # 8 dientes distribuidos alrededor del círculo
    painter.translate(center, center)
    for i in range(8):
        painter.save()
        painter.rotate(i * 45)
        painter.drawRect(QRectF(-tooth_w / 2, -(outer_r + tooth_h * 0.55), tooth_w, tooth_h))
        painter.restore()
    painter.resetTransform()

    # Hueco central (deja transparente el centro, como un engranaje real)
    painter.setCompositionMode(QPainter.CompositionMode_Clear)
    painter.setBrush(QColor(0, 0, 0, 255))
    painter.drawEllipse(QPointF(center, center), inner_r, inner_r)

    painter.end()
    return QIcon(pixmap)


class HeaderBar(QFrame):
    """Barra superior: nombre de la fuente activa + botón de settings"""

    # Señal vacía: solo avisa "se apretó settings", sin pasar datos.
    settings_clicked = Signal()

    def __init__(self, source_name: str = "", parent=None):
        super().__init__(parent)
        # "panel" ya tiene estilo definido en theme.py (fondo + borde).
        self.setObjectName("panel")
        self._build_ui(source_name)

    def _build_ui(self, source_name: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)

        self.source_label = QLabel(source_name.upper())
        self.source_label.setObjectName("monoTag")  # estilo mono + amarillo, de theme.py
        layout.addWidget(self.source_label)

        layout.addStretch()  # empuja el botón de settings hacia la derecha

        self.btn_settings = QPushButton()
        self.btn_settings.setIcon(_create_gear_icon())
        self.btn_settings.setIconSize(QSize(18, 18))
        self.btn_settings.setFixedWidth(32)
        self.btn_settings.setToolTip("Configuración")
        self.btn_settings.clicked.connect(self.settings_clicked.emit)
        layout.addWidget(self.btn_settings)

    def set_source_name(self, name: str):
        """Actualiza el texto de la fuente sin reconstruir el widget entero"""
        self.source_label.setText(name.upper())