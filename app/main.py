"""
Punto de entrada. Ejecutar con:  python -m app.main
"""
import sys

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.ui.theme import build_stylesheet         


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(build_stylesheet())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()