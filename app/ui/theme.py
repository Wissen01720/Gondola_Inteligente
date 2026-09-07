class Colors:
    """Paleta de la app"""
 
    # ---- Fondos (de más oscuro a más claro) -------------------------
    BG_APP = "#141310"        # Fondo general de la ventana
    BG_PANEL = "#1C1B17"      # Tarjetas / paneles (Source Setup, ROI, etc.)
    BG_INPUT = "#0F0E0A"      # Campos de texto, áreas tipo "canvas"
    BG_HOVER = "#26241D"      # Hover sobre filas / botones secundarios
 
    # ---- Bordes / separadores ----------------------------------------
    BORDER = "#332F22"
    BORDER_SOFT = "#242219"
 
    # ---- Acento (amarillo de marca) -----------------------------------
    ACCENT = "#D8C61A"
    ACCENT_HOVER = "#E8D62A"
    ACCENT_PRESSED = "#B8A815"
    ACCENT_TEXT_ON = "#141310"   # texto que va SOBRE fondo amarillo (oscuro, por contraste)
 
    # ---- Texto -----------------------------------------------------------
    TEXT_PRIMARY = "#F2F0E6"
    TEXT_SECONDARY = "#9A9890"
    TEXT_MUTED = "#5F5D54"
 
    # ---- Estados (se usarán en fases futuras: alertas, tracking) --------
    SUCCESS = "#3DDC84"
    WARNING = "#E5A63D"
    DANGER = "#E5484D"
    INFO_BLUE = "#3D9BE5"    # borde de panel "activo", visto en Live Monitoring
 
 
class Fonts:
    """Fuentes reutilizables"""
 
    FAMILY_UI = "Segoe UI"        # texto normal (labels, botones)
    FAMILY_MONO = "Consolas"      # etiquetas tipo "VISION_CORE_05", "VISION_ENGINE v2.4.0"
 
    SIZE_SMALL = 9
    SIZE_NORMAL = 10
    SIZE_LARGE = 13
    SIZE_TITLE = 15
 
 
def build_stylesheet() -> str:
    c = Colors
    f = Fonts
 
    return f"""
    /* ================= Base ================= */
    QWidget {{
        background-color: {c.BG_APP};
        color: {c.TEXT_PRIMARY};
        font-family: "{f.FAMILY_UI}";
        font-size: {f.SIZE_NORMAL}pt;
    }}
 
    QMainWindow {{
        background-color: {c.BG_APP};
    }}
 
    QToolTip {{
        background-color: {c.BG_PANEL};
        color: {c.TEXT_PRIMARY};
        border: 1px solid {c.BORDER};
    }}
 
    /* ================= Paneles / tarjetas =================
       Uso: contenedor.setObjectName("panel")                  */
    QFrame#panel, QWidget#panel {{
        background-color: {c.BG_PANEL};
        border: 1px solid {c.BORDER};
        border-radius: 4px;
    }}
 
    /* ================= Botones normales ================= */
    QPushButton {{
        background-color: {c.BG_PANEL};
        color: {c.TEXT_PRIMARY};
        border: 1px solid {c.BORDER};
        border-radius: 3px;
        padding: 6px 14px;
    }}
    QPushButton:hover {{
        background-color: {c.BG_HOVER};
    }}
    QPushButton:disabled {{
        color: {c.TEXT_MUTED};
    }}
 
    /* ================= Botón primario (amarillo) =================
       Uso: boton.setObjectName("primary")                          */
    QPushButton#primary {{
        background-color: {c.ACCENT};
        color: {c.ACCENT_TEXT_ON};
        border: none;
        font-weight: 600;
    }}
    QPushButton#primary:hover {{
        background-color: {c.ACCENT_HOVER};
    }}
    QPushButton#primary:pressed {{
        background-color: {c.ACCENT_PRESSED};
    }}
    QPushButton#primary:disabled {{
        background-color: {c.BORDER};
        color: {c.TEXT_MUTED};
    }}
 
    /* ================= Toggle de dos opciones =================
       (ej. "IP CAMERA" / "SUBIR ARCHIVO" en los mockups)
       Uso: boton.setObjectName("toggleActive" | "toggleInactive")   */
    QPushButton#toggleActive {{
        background-color: {c.ACCENT};
        color: {c.ACCENT_TEXT_ON};
        border: none;
        font-weight: 600;
    }}
    QPushButton#toggleInactive {{
        background-color: {c.BG_HOVER};
        color: {c.TEXT_SECONDARY};
        border: none;
    }}
 
    /* ================= Campos de texto / listas ================= */
    QLineEdit, QTextEdit, QPlainTextEdit {{
        background-color: {c.BG_INPUT};
        border: 1px solid {c.BORDER};
        border-radius: 3px;
        padding: 4px 6px;
        color: {c.TEXT_PRIMARY};
    }}
 
    QListWidget {{
        background-color: {c.BG_PANEL};
        border: 1px solid {c.BORDER};
    }}
    QListWidget::item {{
        padding: 4px;
    }}
    QListWidget::item:selected {{
        background-color: {c.BG_HOVER};
        color: {c.ACCENT};
    }}
 
    /* ================= Etiquetas especiales =================
       monoTag     -> "VISION_CORE_05" (mono, amarillo, mayúsculas)
       sectionTitle-> títulos de sección ("Source Setup & Configuration")
       mutedText   -> texto secundario / ayuda                          */
    QLabel#monoTag {{
        font-family: "{f.FAMILY_MONO}";
        color: {c.ACCENT};
        font-size: {f.SIZE_SMALL}pt;
        letter-spacing: 1px;
    }}
 
    QLabel#sectionTitle {{
        color: {c.TEXT_PRIMARY};
        font-size: {f.SIZE_LARGE}pt;
        font-weight: 600;
    }}
 
    QLabel#mutedText {{
        color: {c.TEXT_SECONDARY};
        font-size: {f.SIZE_SMALL}pt;
    }}

        QLabel#fieldLabel {{
        font-family: "{f.FAMILY_MONO}";
        color: {c.TEXT_SECONDARY};
        font-size: {f.SIZE_SMALL}pt;
        letter-spacing: 1px;
    }}
 
    /* ================= Barra de progreso ================= */
    QProgressBar {{
        background-color: {c.BG_INPUT};
        border: 1px solid {c.BORDER};
        border-radius: 3px;
        text-align: center;
        color: {c.TEXT_PRIMARY};
    }}
    QProgressBar::chunk {{
        background-color: {c.ACCENT};
    }}
 
    /* ================= Splitter ================= */
    QSplitter::handle {{
        background-color: {c.BORDER};
    }}
 
    /* ================= Scrollbars oscuras ================= */
    QScrollBar:vertical {{
        background: {c.BG_APP};
        width: 10px;
    }}
    QScrollBar::handle:vertical {{
        background: {c.BORDER};
        border-radius: 5px;
        min-height: 20px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
 
    /* ================= Pestañas (QTabWidget) =================*/
    QTabWidget::pane {{
        border: 1px solid {c.BORDER};
        background-color: {c.BG_APP};
    }}
    QTabBar::tab {{
        background-color: {c.BG_PANEL};
        color: {c.TEXT_SECONDARY};
        padding: 8px 16px;
        border: 1px solid {c.BORDER};
        border-bottom: none;
    }}
    QTabBar::tab:selected {{
        background-color: {c.BG_APP};
        color: {c.ACCENT};
    }}
    """