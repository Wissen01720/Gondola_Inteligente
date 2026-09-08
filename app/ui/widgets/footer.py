from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel

from app.utils import config


class FooterBar(QFrame):
    """Barra inferior: versión del motor + métricas en vivo (FPS/CPU)"""

    def __init__(self, engine_version: str = "", parent=None):
        super().__init__(parent)
        engine_version = engine_version or config.ENGINE_VERSION
        self.setObjectName("panel")
        self._build_ui(engine_version)

    def _build_ui(self, engine_version: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)

        self.version_label = QLabel(engine_version)
        self.version_label.setObjectName("mutedText")  # estilo gris/pequeño, de theme.py
        layout.addWidget(self.version_label)

        layout.addStretch()

        self.metrics_label = QLabel("FPS: -- | CPU: --%")
        self.metrics_label.setObjectName("mutedText")
        layout.addWidget(self.metrics_label)

    def update_metrics(self, fps: float, cpu_pct: float):
        """Actualiza el texto de métricas"""
        self.metrics_label.setText(f"FPS: {fps:.1f} | CPU: {cpu_pct:.0f}%")