"""Dark theme built from the design tokens in cliphub-mockup.html (owner: member 1)."""
from __future__ import annotations

import tempfile
from functools import lru_cache
from pathlib import Path
from string import Template

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

# Tokens copied from :root in cliphub-mockup.html. Alpha values are 0-255 for Qt.
APP_BG = "#101010"
SIDEBAR = "#141416"
SURFACE = "#242424"
ELEVATED = "#2e2e30"
INSET = "#0e0e0f"
GLASS = "rgba(28, 28, 30, 148)"
GLASS_2 = "rgba(34, 34, 37, 184)"
RIM = "rgba(255, 255, 255, 26)"
RIM_2 = "rgba(255, 255, 255, 41)"
TEXT = "#f4f3f2"
TEXT_2 = "#a6a29c"
TEXT_3 = "#6d6a66"
ACCENT = "#ff7a1a"
ACCENT_2 = "#ff9147"
ACCENT_PRESS = "#e85f00"
ACCENT_SOFT = "rgba(255, 122, 26, 36)"
ACCENT_LINE = "rgba(255, 122, 26, 107)"
OK = "#34d399"
OK_SOFT = "rgba(52, 211, 153, 36)"
ERR = "#f87171"
INFO = "#60a5fa"
RADIUS_SM = 8
RADIUS = 12
RADIUS_LG = 16
SANS = '"IBM Plex Sans Thai", "SF Pro Text", "Segoe UI", "Helvetica Neue", sans-serif'
MONO = '"IBM Plex Mono", "SF Mono", "Menlo", "Consolas", monospace'

_STYLE_TEMPLATE = Template("""
QWidget { color: $text; font-family: $sans; font-size: 14px; }
QMainWindow, QDialog, QMessageBox, QWidget#Central { background: $app_bg; }
QLabel { background: transparent; }
QToolTip { background: $elevated; color: $text; border: 1px solid $rim_2; padding: 4px 8px; }

/* sidebar */
QFrame#Sidebar { background: $sidebar; border: none; border-right: 1px solid $rim; }
QLabel#BrandMark { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 $accent, stop:1 $accent_press); border-radius: ${r}px; }
QLabel#BrandName { font-size: 16px; font-weight: 600; }
QLabel#BrandVersion { color: $text_3; font-family: $mono; font-size: 11px; }
QLabel#NavLabel { color: $text_3; font-size: 11px; font-weight: 600; padding: 6px 12px 4px 12px; }
QPushButton[nav="true"] { text-align: left; padding: 11px 12px; border: 1px solid transparent; border-radius: ${r}px;
  background: transparent; color: $text_2; font-weight: 500; }
QPushButton[nav="true"]:hover { background: rgba(255, 255, 255, 10); color: $text; }
QPushButton[nav="true"]:checked { background: $accent_soft; border: 1px solid $accent_line; color: $text; }

/* page chrome shared by all feature pages */
QScrollArea { background: transparent; border: none; }
QLabel#PageTitle { font-size: 26px; font-weight: 700; }
QLabel#PageSubtitle { color: $text_2; font-size: 14px; }
QFrame#Card { background: $glass; border: 1px solid $rim; border-radius: ${r_lg}px; }
QLabel#FieldLabel { color: $text_2; font-size: 11px; font-weight: 600; }
QLabel#Hint { color: $text_3; font-family: $mono; font-size: 12px; }
QLabel[state="ok"] { color: $ok; }
QLabel[state="err"] { color: $err; }
QLabel#Chip { padding: 4px 12px; border-radius: 13px; color: $text_2; font-family: $mono; font-size: 12px;
  background: rgba(255, 255, 255, 8); border: 1px solid $rim; }
QLabel#Chip[on="true"] { background: $accent_soft; border: 1px solid $accent_line; color: $text; }

/* inputs */
QLineEdit, QComboBox { background: rgba(10, 10, 11, 166); border: 1px solid $rim; border-radius: ${r}px;
  padding: 0 14px; min-height: 50px; selection-background-color: $accent; selection-color: #1a0f04;
  placeholder-text-color: $text_3; }
QLineEdit:focus, QComboBox:focus { border: 1px solid $accent_line; }
QLineEdit:disabled, QComboBox:disabled { color: $text_3; }
QComboBox QAbstractItemView { background: $elevated; border: 1px solid $rim_2; border-radius: ${r}px; padding: 6px;
  outline: 0; selection-background-color: $accent_soft; selection-color: $text; }
QComboBox QAbstractItemView::item { padding: 8px 10px; min-height: 26px; border-radius: ${r_sm}px; }

/* buttons: plain QPushButton is the ghost style so other pages look right without extra work */
QPushButton { background: $glass_2; color: $text; border: 1px solid $rim_2; border-radius: ${r}px;
  padding: 9px 16px; font-size: 13px; font-weight: 500; }
QPushButton:hover { background: rgba(255, 255, 255, 20); }
QPushButton:pressed { background: rgba(255, 255, 255, 12); }
QPushButton:disabled { color: $text_3; border-color: $rim; }
QPushButton#PrimaryButton { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 $accent_2, stop:1 $accent);
  color: #1a0f04; border: 1px solid transparent; min-height: 30px; padding: 9px 24px; font-size: 14px; font-weight: 600; }
QPushButton#PrimaryButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffa461, stop:1 $accent_2); }
QPushButton#PrimaryButton:pressed { background: $accent_press; }
QPushButton#PrimaryButton:disabled { background: $surface; color: $text_3; }
QFrame#Segmented { background: rgba(10, 10, 11, 153); border: 1px solid $rim; border-radius: ${r}px; }
QPushButton[seg="true"] { background: transparent; border: 1px solid transparent; border-radius: ${r_sm}px;
  color: $text_2; padding: 10px 10px; }
QPushButton[seg="true"]:hover { color: $text; background: transparent; }
QPushButton[seg="true"]:checked { background: $elevated; border: 1px solid $rim_2; color: $text; }

/* downloader metadata preview */
QFrame#Poster { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3a2a1c, stop:0.6 #1a1a1c, stop:1 #1a1a1c);
  border: 1px solid $rim; border-radius: ${r}px; }
QLabel#PosterPlay { background: $accent; border-radius: 23px; }
QLabel#PosterDuration { background: rgba(0, 0, 0, 180); color: #ffffff; font-family: $mono; font-size: 11px;
  padding: 2px 7px; border-radius: 6px; }
QLabel#MetaTitle { font-size: 17px; font-weight: 600; }
QLabel#MetaRow { color: $text_2; font-size: 12px; }

/* queue rail */
QWidget#Rail { background: $sidebar; border-left: 1px solid $rim; }
QLabel#RailTitle { font-size: 14px; font-weight: 600; }
QLabel#CountBadge { color: $accent_2; background: $accent_soft; border: 1px solid $accent_line; border-radius: 10px;
  padding: 2px 8px; font-family: $mono; font-size: 11px; }
QLabel#RailEmpty { color: $text_3; font-size: 13px; padding: 24px 0; }
QLabel#RailFoot { color: $text_3; font-size: 11px; }
QFrame#JobCard { background: $glass; border: 1px solid $rim; border-radius: ${r}px; }
QFrame#JobCard[state="running"] { border: 1px solid $accent_line; }
QFrame#JobCard[state="failed"] { border: 1px solid rgba(248, 113, 113, 90); }
QLabel#JobIcon { background: $accent_soft; border: 1px solid $accent_line; border-radius: ${r_sm}px; }
QLabel#JobIcon[kind="download"] { background: rgba(96, 165, 250, 36); border: 1px solid rgba(96, 165, 250, 77); }
QLabel#JobIcon[kind="subtitle"] { background: rgba(167, 139, 250, 36); border: 1px solid rgba(167, 139, 250, 77); }
QLabel#JobIcon[state="done"] { background: $ok_soft; border: 1px solid rgba(52, 211, 153, 77); }
QLabel#JobTitle { font-size: 13px; font-weight: 600; }
QLabel#JobSummary { color: $text_3; font-family: $mono; font-size: 11px; }
QLabel#JobStatus { color: $text_2; font-size: 11px; }
QLabel#JobPercent { color: $text_2; font-family: $mono; font-size: 11px; }
QPushButton#JobCancel { padding: 0; border-radius: 7px; background: rgba(255, 255, 255, 8); border: 1px solid $rim; }
QPushButton#JobCancel:hover { border: 1px solid rgba(248, 113, 113, 102); background: rgba(248, 113, 113, 30); }
QProgressBar { background: rgba(255, 255, 255, 18); border: none; border-radius: 3px; min-height: 7px; max-height: 7px; }
QProgressBar::chunk { border-radius: 3px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 $accent_2, stop:1 $accent); }
QProgressBar[kind="download"]::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #93c5fd, stop:1 $info); }
QFrame#JobCard[state="done"] QProgressBar::chunk { background: $ok; }
QFrame#JobCard[state="failed"] QProgressBar::chunk { background: $err; }
QFrame#JobCard[state="cancelled"] QProgressBar::chunk { background: $text_3; }

/* scrollbars */
QScrollBar:vertical { background: transparent; width: 9px; margin: 0; }
QScrollBar::handle:vertical { background: rgba(255, 255, 255, 23); border-radius: 4px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: rgba(255, 255, 255, 46); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { height: 0; }
""")

STYLE_SHEET = _STYLE_TEMPLATE.substitute(
    app_bg=APP_BG, sidebar=SIDEBAR, surface=SURFACE, elevated=ELEVATED, glass=GLASS, glass_2=GLASS_2,
    rim=RIM, rim_2=RIM_2, text=TEXT, text_2=TEXT_2, text_3=TEXT_3, accent=ACCENT, accent_2=ACCENT_2,
    accent_press=ACCENT_PRESS, accent_soft=ACCENT_SOFT, accent_line=ACCENT_LINE, ok=OK, ok_soft=OK_SOFT,
    err=ERR, info=INFO, r=RADIUS, r_sm=RADIUS_SM, r_lg=RADIUS_LG, sans=SANS, mono=MONO,
)

# Stroke icons copied from the mockup (24x24 viewBox). Keys match TaskQueue task kinds and PAGES.
_ICONS = {
    "download": '<path d="M12 3v12m0 0 4-4m-4 4-4-4"/><path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>',
    "convert": '<path d="M4 8h13m0 0-4-4m4 4-4 4"/><path d="M20 16H7m0 0 4 4m-4-4 4-4"/>',
    "compress": '<path d="M8 3v3a2 2 0 0 1-2 2H3"/><path d="M21 8h-3a2 2 0 0 1-2-2V3"/>'
                '<path d="M3 16h3a2 2 0 0 1 2 2v3"/><path d="M16 21v-3a2 2 0 0 1 2-2h3"/>',
    "subtitle": '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M7 14h4"/><path d="M13 14h4"/>',
    "queue": '<path d="M4 6h16M4 12h16M4 18h10"/>',
    "close": '<path d="M6 6l12 12M18 6 6 18"/>',
    "link": '<path d="M9.5 14.5l5-5"/><path d="M11 6.5 12.5 5a4 4 0 0 1 5.7 5.7L16.5 12"/>'
            '<path d="M13 17.5 11.5 19a4 4 0 0 1-5.7-5.7L7.5 12"/>',
    "paste": '<rect x="6" y="4" width="12" height="16" rx="2.5"/><path d="M9 4.5h6V7a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1z"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "video": '<rect x="2" y="6" width="14" height="12" rx="2"/><path d="M16 10l6-3v10l-6-3z"/>',
    "audio": '<path d="M4 10v4M8 6v12M12 3v18M16 7v10M20 10v4"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7.5V12l3 1.8"/>',
    "chevron": '<path d="m6 9 6 6 6-6"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "play": '<path d="M8 5l12 7-12 7z" fill="currentColor" stroke="none"/>',
}


@lru_cache(maxsize=None)
def make_icon(name: str, color: str = TEXT_2, size: int = 20, stroke: float = 1.8) -> QIcon:
    """Render one of the mockup icons in the given colour. Needs a QGuiApplication."""
    body = _ICONS.get(name, _ICONS["queue"]).replace("currentColor", color)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
    )
    try:
        from PySide6.QtSvg import QSvgRenderer
    except ImportError:  # QtSvg missing: the UI still works, just without icons
        return QIcon()
    scale = 2  # crisp on high-DPI screens
    pixmap = QPixmap(size * scale, size * scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(scale)
    painter = QPainter(pixmap)
    QSvgRenderer(svg.encode("utf-8")).render(painter, QRectF(0, 0, size, size))
    painter.end()
    return QIcon(pixmap)


def repolish(widget: QWidget) -> None:
    """Re-apply the stylesheet after a dynamic property (state, on, kind) changed."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def _dark_palette() -> QPalette:
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: APP_BG,
        QPalette.ColorRole.WindowText: TEXT,
        QPalette.ColorRole.Base: INSET,
        QPalette.ColorRole.AlternateBase: SURFACE,
        QPalette.ColorRole.Text: TEXT,
        QPalette.ColorRole.Button: SURFACE,
        QPalette.ColorRole.ButtonText: TEXT,
        QPalette.ColorRole.ToolTipBase: ELEVATED,
        QPalette.ColorRole.ToolTipText: TEXT,
        QPalette.ColorRole.PlaceholderText: TEXT_3,
        QPalette.ColorRole.Highlight: ACCENT,
        QPalette.ColorRole.HighlightedText: "#1a0f04",
    }
    for role, value in roles.items():
        palette.setColor(role, QColor(value))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(TEXT_3))
    return palette


def _combo_arrow_rule() -> str:
    """QSS can only show a custom drop-down arrow from a file, so write the chevron to the temp dir."""
    try:
        folder = Path(tempfile.gettempdir()) / "cliphub-ui"
        folder.mkdir(exist_ok=True)
        path = folder / "chevron-down.png"
        if not make_icon("chevron", TEXT_2, 14, 2.0).pixmap(14, 14).save(str(path), "PNG"):
            return ""
    except OSError:
        return ""
    return (
        "QComboBox::drop-down { border: none; width: 30px; background: transparent; }"
        f"QComboBox::down-arrow {{ image: url({path.as_posix()}); width: 14px; height: 14px; }}"
    )


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")  # consistent base so the stylesheet renders the same on Windows and macOS
    app.setPalette(_dark_palette())
    app.setStyleSheet(STYLE_SHEET + _combo_arrow_rule())
