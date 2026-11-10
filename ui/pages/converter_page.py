"""Feature 2 page: converter and audio separator UI (owner: member 2)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    Property, QByteArray, QEasingCurve, QPointF, QPropertyAnimation, QRectF, QSize, Qt,
    QThread, QTimer, Signal,
)
from PySide6.QtGui import (
    QColor, QDragEnterEvent, QDropEvent, QIcon, QPainter, QPen, QPixmap, QStandardItem,
    QStandardItemModel,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QGraphicsDropShadowEffect,
    QHBoxLayout, QLabel, QListView, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from core.errors import ClipHubError
from core.ffmpeg import probe_duration
from tasks.converter import (
    SEPARATOR_FORMATS, VIDEO_TARGETS, ConverterTask, audio_sidecar_path,
    describe_conversion, suggest_output_path,
)

_VIDEO_EXTS = "*.mp4 *.mkv *.avi *.mov *.webm *.m4v *.flv *.wmv *.ts"
_AUDIO_EXTS = "*.mp3 *.wav *.aac *.flac *.m4a *.ogg *.opus *.wma"
FILE_FILTERS = ";;".join([
    f"ไฟล์วิดีโอและเสียง ({_VIDEO_EXTS} {_AUDIO_EXTS})",
    f"ไฟล์วิดีโอ ({_VIDEO_EXTS})",
    f"ไฟล์เสียง ({_AUDIO_EXTS})",
    "ทุกไฟล์ (*)",
])

# Mockup tokens (cliphub-mockup.html :root) as QSS-friendly values.
_ACCENT = "#ff7a1a"
_STYLE = """
QLabel { background: transparent; color: #f4f3f2; }
QLabel#pageTitle { font-size: 26px; font-weight: 700; }
QLabel#pageSubtitle { font-size: 14px; color: #a6a29c; }
QLabel#badge { font-size: 12px; color: #a6a29c; padding: 7px 13px; border-radius: 16px;
    background: rgba(28,28,30,148); border: 1px solid rgba(255,255,255,26); }
QLabel#fieldLabel { font-size: 11px; font-weight: 600; color: #a6a29c; }
QLabel#muted, QLabel#hint { font-size: 12px; color: #6d6a66; }
QLabel#hint, QLabel#mono, QLabel#fileMeta, QLabel#fileSize, QLabel#outName {
    font-family: "IBM Plex Mono", "SF Mono", Menlo, Consolas, monospace; }
QLabel#hint { font-size: 13px; }
QLabel#fileMeta { font-size: 12px; color: #6d6a66; }
QLabel#fileSize { font-size: 13px; color: #a6a29c; }
QLabel#fileName { font-size: 14px; font-weight: 600; }
QLabel#outName { font-size: 13px; color: #f4f3f2; }
QLabel#toggleTitle { font-size: 14px; font-weight: 600; }
QLabel#errorText { font-size: 13px; color: #f87171; }
QLabel#okText { font-size: 13px; color: #34d399; }
QLabel#noticeText { font-size: 13px; color: #a6a29c; }
QLabel#dzTitle { font-size: 16px; font-weight: 600; }
QLabel#dzSub { font-size: 13px; color: #6d6a66; }
QLabel#dzIcon { background: rgba(255,122,26,36); border: 1px solid rgba(255,122,26,107);
    border-radius: 16px; }
QLabel#thumb { border-radius: 8px; background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
    stop:0 #2a2a2d, stop:1 #1b1b1d); }

QFrame#card { background: rgba(28,28,30,148); border: 1px solid rgba(255,255,255,26);
    border-radius: 16px; }
QFrame#fileRow { background: rgba(255,255,255,7); border: 1px solid rgba(255,255,255,26);
    border-radius: 12px; }
QFrame#dropzone { border: 1px dashed rgba(255,255,255,41); border-radius: 16px;
    background: rgba(255,122,26,10); }
QFrame#dropzone:hover, QFrame#dropzone[drag="true"] {
    border-color: rgba(255,122,26,107); background: rgba(255,122,26,30); }

QPushButton#ghost { background: rgba(34,34,37,184); color: #f4f3f2; font-size: 13px;
    border: 1px solid rgba(255,255,255,41); border-radius: 12px; padding: 9px 15px; }
QPushButton#ghost:hover { background: rgba(255,255,255,20); }
QPushButton#ghost:pressed { background: rgba(255,255,255,30); }
QPushButton#primary { color: #1a0f04; font-size: 14px; font-weight: 600; border: none;
    border-radius: 12px; padding: 0 22px; min-height: 48px;
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ff9147, stop:1 #ff7a1a); }
QPushButton#primary:hover { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
    stop:0 #ffa05f, stop:1 #ff8430); }
QPushButton#primary:pressed { background: #e85f00; }
QPushButton#primary:disabled { background: rgba(255,255,255,18); color: #6d6a66; }

QComboBox { min-height: 52px; padding: 0 40px 0 16px; font-size: 14px; color: #f4f3f2;
    border-radius: 12px; border: 1px solid rgba(255,255,255,26);
    background: rgba(10,10,11,166); }
QComboBox:hover { border-color: rgba(255,255,255,41); }
QComboBox:focus, QComboBox:on { border-color: rgba(255,122,26,107); }
QComboBox:disabled { color: #6d6a66; }
QComboBox::drop-down { border: none; width: 36px; }
QComboBox#fmtCombo { min-height: 36px; min-width: 56px; padding: 0 34px 0 12px; font-size: 13px; }
QComboBox QAbstractItemView { background: #1f1f21; color: #a6a29c; font-size: 14px;
    border: 1px solid rgba(255,255,255,41); border-radius: 8px; padding: 6px; outline: 0;
    selection-background-color: rgba(255,255,255,18); selection-color: #f4f3f2; }
QComboBox QAbstractItemView::item { min-height: 32px; padding: 0 10px; border-radius: 6px; }
QComboBox QAbstractItemView::item:disabled { color: #6d6a66; font-size: 11px; }
"""

_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="currentColor" stroke-width="{w}" stroke-linecap="round" '
    'stroke-linejoin="round">{body}</svg>'
)
_ICON_UPLOAD = (
    '<path d="M12 15V3m0 0 4 4m-4-4-4 4"/>'
    '<path d="M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/>'
)
_ICON_FILM = (
    '<rect x="3" y="5" width="18" height="14" rx="2"/>'
    '<path d="m10 9 5 3-5 3z" fill="currentColor" stroke="none"/>'
)
_ICON_SWAP = '<path d="M4 8h13m0 0-4-4m4 4-4 4"/><path d="M20 16H7m0 0 4 4m-4-4 4-4"/>'


def _icon_pixmap(body: str, size: int, color: str, width: float = 1.8) -> QPixmap:
    ratio = 2.0
    svg = _SVG.format(w=width, body=body).replace("currentColor", color)
    pixmap = QPixmap(int(size * ratio), int(size * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    QSvgRenderer(QByteArray(svg.encode("utf-8"))).render(painter, QRectF(0, 0, size, size))
    painter.end()
    return pixmap


def format_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            digits = 0 if unit == "B" or size >= 100 else 1
            return f"{size:.{digits}f} {unit}"
        size /= 1024
    return f"{num_bytes} B"


def format_duration(seconds: float) -> str:
    total = int(round(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


class _ProbeThread(QThread):
    """Reads size and duration of the chosen file so the GUI thread never touches the disk."""

    probed = Signal(int, object)  # serial, {"size": int | None, "duration": float | None, "error": str | None}

    def __init__(self, serial: int, path: str) -> None:
        super().__init__()
        self._serial = serial
        self._path = path

    def run(self) -> None:
        info: dict[str, object] = {"size": None, "duration": None, "error": None}
        try:
            info["size"] = Path(self._path).stat().st_size
            info["duration"] = probe_duration(self._path)
        except ClipHubError as exc:
            info["error"] = str(exc)
        except OSError as exc:
            info["error"] = f"อ่านไฟล์ไม่ได้: {exc.strerror or exc}"
        self.probed.emit(self._serial, info)


class _ElidedLabel(QLabel):
    """Single-line label that shortens the middle of long file names."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full = text
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.set_full_text(text)

    def set_full_text(self, text: str) -> None:
        self._full = text
        self.setToolTip(text)
        self._elide()

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        width = max(self.width(), 10)
        self.setText(self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideMiddle, width))


class _Combo(QComboBox):
    """QComboBox with a painted chevron (QSS cannot draw one without an image file)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setView(QListView())
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt API)
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor("#a6a29c" if self.isEnabled() else "#4a4846")
        painter.setPen(QPen(color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        cx, cy = self.width() - 20.0, self.height() / 2
        painter.drawPolyline([QPointF(cx - 4.5, cy - 2.5), QPointF(cx, cy + 2.5),
                              QPointF(cx + 4.5, cy - 2.5)])


class SwitchCheckBox(QCheckBox):
    """A QCheckBox drawn as the mockup's pill switch (46x27). The text is for accessibility only."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setFixedSize(46, 27)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._offset = 1.0 if self.isChecked() else 0.0
        self._animation = QPropertyAnimation(self, b"offset", self)
        self._animation.setDuration(180)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def _animate(self, checked: bool) -> None:
        self._animation.stop()
        self._animation.setStartValue(self._offset)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()

    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, value: float) -> None:
        self._offset = value
        self.update()

    offset = Property(float, _get_offset, _set_offset)

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt API)
        return QSize(46, 27)

    def hitButton(self, pos) -> bool:  # noqa: N802 (Qt API)
        return self.rect().contains(pos)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt API)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            painter.setOpacity(0.4)
        mix = self._offset
        off, on = QColor(255, 255, 255, 26), QColor(_ACCENT)
        track = QColor(
            round(off.red() + (on.red() - off.red()) * mix),
            round(off.green() + (on.green() - off.green()) * mix),
            round(off.blue() + (on.blue() - off.blue()) * mix),
            round(off.alpha() + (on.alpha() - off.alpha()) * mix),
        )
        border = QColor(255, 122, 26, 107) if self.hasFocus() else QColor(255, 255, 255, 26)
        painter.setPen(QPen(border, 1))
        painter.setBrush(track)
        painter.drawRoundedRect(QRectF(0.5, 0.5, 45, 26), 13.5, 13.5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#e8e8e8"))
        painter.drawEllipse(QRectF(3.0 + 19.0 * mix, 3.0, 21, 21))


class _DropZone(QFrame):
    """Dashed target that takes one file by drag and drop, click or the browse button."""

    file_dropped = Signal(str, int)  # first path, number of files dropped
    drop_rejected = Signal(str)      # Thai message
    browse_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dropzone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        icon = QLabel()
        icon.setObjectName("dzIcon")
        icon.setFixedSize(60, 60)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setPixmap(_icon_pixmap(_ICON_UPLOAD, 28, _ACCENT))
        title = QLabel("ลากไฟล์วิดีโอมาวางที่นี่")
        title.setObjectName("dzTitle")
        # two fixed lines instead of word wrap: wrapped labels in nested layouts get clipped
        sub = QLabel("รองรับ MP4 · MKV · AVI · MOV · WEBM\nและไฟล์เสียง MP3 · WAV · AAC · FLAC")
        sub.setObjectName("dzSub")
        self.browse_button = QPushButton("เลือกไฟล์จากเครื่อง")
        self.browse_button.setObjectName("ghost")
        self.browse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_button.clicked.connect(self.browse_requested)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 30, 24, 28)
        layout.setSpacing(6)
        for widget in (icon, title, sub):
            layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(8)
        layout.addWidget(self.browse_button, 0, Qt.AlignmentFlag.AlignHCenter)
        for label in (title, sub):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _set_drag(self, active: bool) -> None:
        self.setProperty("drag", active)
        self.style().unpolish(self)
        self.style().polish(self)

    @staticmethod
    def _local_paths(event) -> list[str]:
        return [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 (Qt API)
        if self._local_paths(event):
            event.acceptProposedAction()
            self._set_drag(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802 (Qt API)
        self._set_drag(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 (Qt API)
        self._set_drag(False)
        paths = self._local_paths(event)
        if not paths:
            self.drop_rejected.emit("วางได้เฉพาะไฟล์จากเครื่องนี้")
            return
        if Path(paths[0]).is_dir():
            self.drop_rejected.emit("ไม่รองรับโฟลเดอร์ กรุณาเลือกไฟล์เดียว")
            return
        event.acceptProposedAction()
        self.file_dropped.emit(paths[0], len(paths))

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if event.button() == Qt.MouseButton.LeftButton:
            self.browse_requested.emit()
        super().mousePressEvent(event)


def _card(tight: bool = False) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    margin = 16 if tight else 20
    layout.setContentsMargins(margin, margin, margin, margin)
    layout.setSpacing(12)
    return frame, layout


def _label(text: str, name: str = "") -> QLabel:
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    return label


class ConverterPage(QWidget):
    task_submitted = Signal(object)  # ConverterTask

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ConverterPage")
        self.setStyleSheet(_STYLE)
        self._input_path: str | None = None
        self._ready = False          # probe finished OK for the current file
        self._serial = 0
        self._probes: list[_ProbeThread] = []
        self._reserved: set[Path] = set()  # outputs of queued jobs that are not on disk yet
        self._last_dir = str(Path.home())
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(lambda: self.status_label.setText(""))

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)
        root.addLayout(self._build_header())
        root.addWidget(self._build_drop_card())
        root.addWidget(self._build_file_card())
        root.addWidget(self._build_target_card())
        root.addWidget(self._build_separator_card())
        root.addLayout(self._build_actions())
        root.addStretch(1)

        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._wait_probes)
        self._refresh()

    # ----- layout -------------------------------------------------------------------
    def _build_header(self) -> QHBoxLayout:
        text = QVBoxLayout()
        text.setSpacing(6)
        text.addWidget(_label("แปลงฟอร์แมต & แยกเสียง", "pageTitle"))
        # fixed line breaks, not word wrap: wrapped labels make the page height depend on its
        # width, and nested layouts then squeeze the cards below
        subtitle = _label(
            "เปลี่ยนนามสกุลไฟล์วิดีโอหรือเสียง\n"
            "และแยกสตรีมเสียงออกจากวิดีโอโดยไม่ทำให้ต้นฉบับเสียหาย\n"
            "ทำงานออฟไลน์เต็มรูปแบบ", "pageSubtitle")
        subtitle.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        text.addWidget(subtitle)
        row = QHBoxLayout()
        row.setSpacing(16)
        row.addLayout(text, 1)
        row.addWidget(_label("ประมวลผลด้วย FFmpeg", "badge"), 0, Qt.AlignmentFlag.AlignTop)
        return row

    def _build_drop_card(self) -> QFrame:
        card, layout = _card()
        self.dropzone = _DropZone()
        self.dropzone.file_dropped.connect(self._on_file_dropped)
        self.dropzone.drop_rejected.connect(lambda message: self._set_notice(message, error=True))
        self.dropzone.browse_requested.connect(self._browse)
        self.notice_label = _ElidedLabel()
        self.notice_label.setObjectName("noticeText")
        self.notice_label.hide()
        layout.addWidget(self.dropzone)
        layout.addWidget(self.notice_label)
        return card

    def _build_file_card(self) -> QFrame:
        self.file_card, layout = _card(tight=True)
        self.file_card.hide()
        row_frame = QFrame()
        row_frame.setObjectName("fileRow")
        row = QHBoxLayout(row_frame)
        row.setContentsMargins(14, 14, 14, 14)
        row.setSpacing(14)

        thumb = QLabel()
        thumb.setObjectName("thumb")
        thumb.setFixedSize(64, 44)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setPixmap(_icon_pixmap(_ICON_FILM, 22, "#6d6a66", width=1.6))
        meta = QVBoxLayout()
        meta.setSpacing(2)
        self.file_name_label = _ElidedLabel()
        self.file_name_label.setObjectName("fileName")
        self.file_meta_label = _label("", "fileMeta")
        meta.addWidget(self.file_name_label)
        meta.addWidget(self.file_meta_label)
        self.file_size_label = _label("", "fileSize")

        row.addWidget(thumb)
        row.addLayout(meta, 1)
        row.addWidget(self.file_size_label)
        self.file_error_label = _ElidedLabel()
        self.file_error_label.setObjectName("errorText")
        self.file_error_label.hide()
        layout.addWidget(row_frame)
        layout.addWidget(self.file_error_label)
        return self.file_card

    def _build_target_card(self) -> QFrame:
        card, layout = _card()
        grid = QHBoxLayout()
        grid.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(9)
        left.addWidget(_label("แปลงเป็น", "fieldLabel"))
        self.target_combo = _Combo()
        model = QStandardItemModel(self.target_combo)
        groups = (
            ("วิดีโอ", [("MP4 (H.264)", "mp4"), ("MKV", "mkv"), ("AVI", "avi"), ("MOV", "mov")]),
            ("เสียง", [("MP3", "mp3"), ("WAV", "wav"), ("AAC", "aac"), ("FLAC", "flac")]),
        )
        for title, entries in groups:
            header = QStandardItem(title)
            header.setFlags(Qt.ItemFlag.NoItemFlags)  # group heading, not selectable
            model.appendRow(header)
            for text, ext in entries:
                item = QStandardItem(text)
                item.setData(ext, Qt.ItemDataRole.UserRole)
                model.appendRow(item)
        self.target_combo.setModel(model)
        self.target_combo.setCurrentIndex(1)  # MP4
        self.target_combo.currentIndexChanged.connect(self._refresh)
        left.addWidget(self.target_combo)

        right = QVBoxLayout()
        right.setSpacing(9)
        right.addWidget(_label("ไฟล์ผลลัพธ์", "fieldLabel"))
        self.output_label = _ElidedLabel()
        self.output_label.setObjectName("outName")
        self.output_label.setMinimumHeight(52)
        right.addWidget(self.output_label)

        grid.addLayout(left, 1)
        grid.addLayout(right, 1)
        layout.addLayout(grid)
        return card

    def _build_separator_card(self) -> QFrame:
        card, layout = _card()
        row = QHBoxLayout()
        row.setSpacing(14)
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(_label("แยกสตรีมเสียงออกจากวิดีโอ", "toggleTitle"))
        self.separator_hint = _label("", "muted")
        text.addWidget(self.separator_hint)

        self.audio_format_combo = _Combo()
        self.audio_format_combo.setObjectName("fmtCombo")
        for ext in SEPARATOR_FORMATS:
            self.audio_format_combo.addItem(ext.upper(), ext)
        self.audio_format_combo.currentIndexChanged.connect(self._refresh)
        self.extract_switch = SwitchCheckBox("แยกสตรีมเสียงออกจากวิดีโอ")
        self.extract_switch.toggled.connect(self._refresh)

        row.addLayout(text, 1)
        row.addWidget(self.audio_format_combo, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.extract_switch, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(row)
        return card

    def _build_actions(self) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setSpacing(8)
        row = QHBoxLayout()
        row.setSpacing(18)
        self.start_button = QPushButton("เริ่มแปลงไฟล์")
        self.start_button.setObjectName("primary")
        self.start_button.setIcon(QIcon(_icon_pixmap(_ICON_SWAP, 19, "#1a0f04", width=2.0)))
        self.start_button.setIconSize(QSize(19, 19))
        self.start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_button.clicked.connect(self._submit)
        self._glow = QGraphicsDropShadowEffect(self.start_button)
        self._glow.setBlurRadius(26)
        self._glow.setOffset(0, 4)
        self._glow.setColor(QColor(255, 122, 26, 110))
        self.start_button.setGraphicsEffect(self._glow)
        self.hint_label = _label("", "hint")
        row.addWidget(self.start_button)
        row.addWidget(self.hint_label, 1)
        self.status_label = _label("", "okText")
        box.addLayout(row)
        box.addWidget(self.status_label)
        return box

    # ----- state --------------------------------------------------------------------
    def target_ext(self) -> str:
        return str(self.target_combo.currentData(Qt.ItemDataRole.UserRole) or "mp4")

    def _extract_active(self) -> bool:
        return self.extract_switch.isChecked() and self.target_ext() in VIDEO_TARGETS

    def _sidecar_format(self) -> str | None:
        if not self._extract_active():
            return None
        return str(self.audio_format_combo.currentData() or "mp3")

    def _refresh(self, *_args: object) -> None:
        ext = self.target_ext()
        is_video = ext in VIDEO_TARGETS
        self.extract_switch.setEnabled(is_video)
        self.audio_format_combo.setEnabled(is_video and self.extract_switch.isChecked())
        self.separator_hint.setText(
            "บันทึกเป็น MP3 / WAV — วิดีโอต้นฉบับไม่ถูกแก้ไข" if is_video else
            "ใช้ได้เมื่อเลือกแปลงเป็นฟอร์แมตวิดีโอ"
        )
        ready = self._input_path is not None and self._ready
        self.start_button.setEnabled(ready)
        self._glow.setEnabled(ready)
        if self._input_path is None:
            self.output_label.set_full_text("—")
            self.hint_label.setText("เลือกไฟล์ต้นทางก่อนเริ่มแปลง")
            return
        sidecar = self._sidecar_format()
        output = suggest_output_path(
            self._input_path, ext, sidecar_ext=sidecar, taken=self._reserved
        )
        self.output_label.set_full_text(output.name)
        self.hint_label.setText(
            describe_conversion(Path(self._input_path).suffix, ext, sidecar)
        )

    def _set_notice(self, message: str, error: bool = False) -> None:
        self.notice_label.setObjectName("errorText" if error else "noticeText")
        self.notice_label.style().unpolish(self.notice_label)
        self.notice_label.style().polish(self.notice_label)
        self.notice_label.set_full_text(message)
        self.notice_label.setVisible(bool(message))

    # ----- choosing a file ----------------------------------------------------------
    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "เลือกไฟล์วิดีโอหรือเสียง", self._last_dir, FILE_FILTERS
        )
        if path:
            self.set_input_file(path)

    def _on_file_dropped(self, path: str, count: int) -> None:
        self.set_input_file(path)
        if count > 1:
            self._set_notice(f"รับครั้งละ 1 ไฟล์ — ใช้ไฟล์แรก ({Path(path).name})")

    def set_input_file(self, path: str) -> None:
        """Select the file to convert; size and duration are read in a QThread."""
        self._set_notice("")
        self._input_path = path
        self._ready = False
        self._last_dir = str(Path(path).parent)
        self._serial += 1
        self._reap_probes()
        self.file_card.show()
        self.file_name_label.set_full_text(Path(path).name)
        self.file_meta_label.setText("กำลังอ่านข้อมูลไฟล์…")
        self.file_size_label.setText("")
        self.file_error_label.hide()
        self.status_label.setText("")
        probe = _ProbeThread(self._serial, path)
        probe.probed.connect(self._on_probed)
        probe.finished.connect(self._reap_probes)
        self._probes.append(probe)
        probe.start()
        self._refresh()

    def _on_probed(self, serial: int, info: dict) -> None:
        if serial != self._serial:
            return  # the user picked another file meanwhile
        if info.get("size") is not None:
            self.file_size_label.setText(format_size(int(info["size"])))
        error = info.get("error")
        if error:
            self._ready = False
            self.file_meta_label.setText("ความยาว —")
            self.file_error_label.set_full_text(str(error))
            self.file_error_label.show()
        else:
            self._ready = True
            self.file_meta_label.setText(f"ความยาว {format_duration(float(info['duration']))}")
        self._refresh()

    def _reap_probes(self) -> None:
        for probe in list(self._probes):
            if probe.wait(0):  # finished; the rest are swept on the next call
                self._probes.remove(probe)
                probe.deleteLater()

    def _wait_probes(self) -> None:
        for probe in list(self._probes):
            probe.wait(3000)

    # ----- submit -------------------------------------------------------------------
    def build_task(self) -> ConverterTask | None:
        """Create the task for the current selection and reserve its output names."""
        if self._input_path is None or not self._ready:
            return None
        ext = self.target_ext()
        sidecar = self._sidecar_format()
        output = suggest_output_path(
            self._input_path, ext, sidecar_ext=sidecar, taken=self._reserved
        )
        self._reserved.add(output)
        if sidecar:
            self._reserved.add(audio_sidecar_path(output, sidecar))
        return ConverterTask(
            self._input_path, str(output),
            extract_audio=sidecar is not None, audio_format=sidecar or "mp3",
        )

    def _submit(self) -> None:
        task = self.build_task()
        if task is None:
            return
        self.task_submitted.emit(task)
        self.status_label.setText(f"เพิ่มงานเข้าคิวแล้ว: {Path(task.output_path).name}")
        self._status_timer.start(5000)
        self._refresh()  # the preview moves on to the next free name
