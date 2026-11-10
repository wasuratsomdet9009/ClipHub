"""Feature 4 page: subtitle UI with transcript preview (owner: member 4)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFontDatabase
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.errors import ClipHubError
from tasks.subtitle import Cue, SubtitleTask, format_srt_time, write_subtitles

AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma"}
VIDEO_SUFFIXES = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".flv", ".wmv"}
MEDIA_FILTER = (
    "ไฟล์เสียงและวิดีโอ ("
    + " ".join(f"*{s}" for s in sorted(AUDIO_SUFFIXES | VIDEO_SUFFIXES))
    + ");;ทุกไฟล์ (*)"
)

LANGUAGES = (("th", "ไทย"), ("en", "English"))
MODELS = (("tiny", "เร็วสุด"), ("base", "สมดุล"), ("small", "แม่นยำ"))
DEFAULT_MODEL = "base"

_STYLE = """
QFrame#card { background: rgba(28, 28, 30, 60%); border: 1px solid rgba(255, 255, 255, 10%); border-radius: 16px; }
QLabel { background: transparent; }
QLabel#pageTitle { font-size: 26px; font-weight: 700; color: #f4f3f2; }
QLabel#pageLead { font-size: 14px; color: #a6a29c; }
QLabel#badge { color: #f4f3f2; font-size: 12px; background: rgba(255, 122, 26, 14%);
    border: 1px solid rgba(255, 122, 26, 42%); border-radius: 15px; padding: 6px 13px; }
QLabel#fieldLabel { font-size: 11px; font-weight: 600; color: #a6a29c; }
QLabel#hint { font-size: 12px; color: #6d6a66; }
QLabel#status { font-size: 12.5px; color: #a6a29c; }
QFrame#fileRow { background: rgba(255, 255, 255, 3%); border: 1px solid rgba(255, 255, 255, 10%); border-radius: 12px; }
QLabel#fileThumb { background: #2a2440; color: #a78bfa; border-radius: 8px; font-size: 20px; }
QLabel#fileName { font-size: 13.5px; font-weight: 600; color: #f4f3f2; }
QLabel#fileMeta { font-size: 12px; color: #6d6a66; }
QLabel#fileSize { font-size: 12.5px; color: #a6a29c; }
QFrame#seg { background: rgba(10, 10, 11, 60%); border: 1px solid rgba(255, 255, 255, 10%); border-radius: 12px; }
QPushButton#segButton { background: transparent; color: #a6a29c; border: 1px solid transparent;
    border-radius: 8px; padding: 10px 14px; font-size: 13.5px; font-weight: 500; }
QPushButton#segButton:hover { color: #f4f3f2; }
QPushButton#segButton:checked { background: #2e2e30; color: #f4f3f2; border-color: rgba(255, 255, 255, 16%); }
QComboBox { background: rgba(10, 10, 11, 60%); color: #f4f3f2; border: 1px solid rgba(255, 255, 255, 10%);
    border-radius: 12px; padding: 10px 14px; font-size: 13.5px; min-height: 22px; }
QComboBox:hover { border-color: rgba(255, 255, 255, 16%); }
QComboBox QAbstractItemView { background: #2e2e30; color: #f4f3f2; border: 1px solid rgba(255, 255, 255, 16%);
    selection-background-color: rgba(255, 122, 26, 14%); selection-color: #f4f3f2; outline: none; }
QLabel#chip { font-size: 12px; color: #a6a29c; background: rgba(255, 255, 255, 3%);
    border: 1px solid rgba(255, 255, 255, 10%); border-radius: 12px; padding: 4px 13px; }
QLabel#chip[on="true"] { color: #f4f3f2; background: rgba(255, 122, 26, 14%); border-color: rgba(255, 122, 26, 42%); }
QLabel#empty { color: #6d6a66; font-size: 13px; padding: 28px 12px; }
QTableWidget { background: transparent; border: none; color: #f4f3f2; font-size: 13.5px; outline: none; }
QTableWidget::item { padding: 6px 8px; border: none; }
QTableWidget::item:selected { background: rgba(255, 122, 26, 14%); color: #f4f3f2; }
QHeaderView { background: transparent; border: none; }
QHeaderView::section { background: transparent; color: #6d6a66; border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 10%); padding: 6px 8px; font-size: 11px; font-weight: 600; }
QPushButton#primary { color: #1a0f04; font-size: 14px; font-weight: 600; min-height: 48px; padding: 0 24px;
    border: none; border-radius: 12px;
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #ff9147, stop: 1 #ff7a1a); }
QPushButton#primary:pressed { background: #e85f00; }
QPushButton#primary:disabled { color: rgba(26, 15, 4, 55%); background: rgba(255, 122, 26, 25%); }
QPushButton#ghost { color: #f4f3f2; font-size: 13px; font-weight: 500; min-height: 48px; padding: 0 18px;
    background: rgba(34, 34, 37, 72%); border: 1px solid rgba(255, 255, 255, 16%); border-radius: 12px; }
QPushButton#ghost:hover { background: rgba(255, 255, 255, 8%); }
QPushButton#ghost:disabled { color: #6d6a66; border-color: rgba(255, 255, 255, 10%); }
QPushButton#pick { color: #f4f3f2; font-size: 13px; font-weight: 500; padding: 9px 15px;
    background: rgba(34, 34, 37, 72%); border: 1px solid rgba(255, 255, 255, 16%); border-radius: 12px; }
QPushButton#pick:hover { background: rgba(255, 255, 255, 8%); }
"""


def _format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def _label(text: str, name: str, wrap: bool = False) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setWordWrap(wrap)
    return label


class SubtitlePage(QWidget):
    task_submitted = Signal(object)  # SubtitleTask

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SubtitlePage")
        self._input_path: str | None = None
        self._task: SubtitleTask | None = None          # last task submitted from this page
        self._preview_task: SubtitleTask | None = None  # task whose cues are in the table
        self._cues: tuple[Cue, ...] = ()
        self._last_dir = str(Path.home())
        self._build_ui()
        self.setStyleSheet(_STYLE)

    # ---- UI construction ------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        head = QHBoxLayout()
        head.setSpacing(16)
        titles = QVBoxLayout()
        titles.setSpacing(6)
        titles.addWidget(_label("ถอดเสียง & สร้างซับไตเติล", "pageTitle"))
        titles.addWidget(_label(
            "แปลงเสียงพูดเป็นข้อความด้วย AI (faster-whisper) พร้อมซิงก์ Timecode อัตโนมัติ "
            "รองรับไทย/อังกฤษ ส่งออกเป็น .srt และ .vtt",
            "pageLead", wrap=True,
        ))
        head.addLayout(titles, 1)
        head.addWidget(_label("faster-whisper", "badge"), 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(head)

        root.addWidget(self._build_file_card())
        root.addWidget(self._build_options_card())
        root.addWidget(self._build_preview_card(), 1)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        self._submit_btn = QPushButton("ถอดเสียงด้วย AI")
        self._submit_btn.setObjectName("primary")
        self._submit_btn.setEnabled(False)
        self._submit_btn.clicked.connect(self._submit)
        self._export_srt_btn = QPushButton("ส่งออก .srt")
        self._export_vtt_btn = QPushButton("ส่งออก .vtt")
        for button, suffix in ((self._export_srt_btn, ".srt"), (self._export_vtt_btn, ".vtt")):
            button.setObjectName("ghost")
            button.setEnabled(False)
            button.clicked.connect(lambda _checked=False, s=suffix: self._export(s))
        for button in (self._submit_btn, self._export_srt_btn, self._export_vtt_btn):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            actions.addWidget(button)
        actions.addStretch(1)
        root.addLayout(actions)

        self._status = _label("", "status", wrap=True)
        root.addWidget(self._status)
        self._set_status("")
        self._refresh_preview_state()

    def _build_file_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(16, 16, 16, 16)

        row = QFrame()
        row.setObjectName("fileRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        self._thumb = _label("♪", "fileThumb")
        self._thumb.setFixedSize(64, 44)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        meta = QVBoxLayout()
        meta.setSpacing(2)
        self._file_name = _label("ยังไม่ได้เลือกไฟล์", "fileName")
        self._file_meta = _label("เลือกไฟล์เสียงหรือวิดีโอที่ต้องการถอดเสียง", "fileMeta")
        meta.addWidget(self._file_name)
        meta.addWidget(self._file_meta)
        self._file_size = _label("", "fileSize")
        pick = QPushButton("เลือกไฟล์")
        pick.setObjectName("pick")
        pick.setCursor(Qt.CursorShape.PointingHandCursor)
        pick.clicked.connect(self._choose_file)

        layout.addWidget(self._thumb)
        layout.addLayout(meta, 1)
        layout.addWidget(self._file_size)
        layout.addWidget(pick)
        outer.addWidget(row)
        return card

    def _build_options_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        grid = QGridLayout(card)
        grid.setContentsMargins(20, 18, 20, 18)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(9)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        grid.addWidget(_label("ภาษาที่พูด", "fieldLabel"), 0, 0)
        grid.addWidget(_label("ขนาดโมเดล AI", "fieldLabel"), 0, 1)

        seg = QFrame()
        seg.setObjectName("seg")
        seg_layout = QHBoxLayout(seg)
        seg_layout.setContentsMargins(4, 4, 4, 4)
        seg_layout.setSpacing(4)
        self._lang_group = QButtonGroup(self)
        self._lang_group.setExclusive(True)
        self._lang_buttons: dict[str, QPushButton] = {}
        for code, text in LANGUAGES:
            button = QPushButton(text)
            button.setObjectName("segButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self._lang_group.addButton(button)
            self._lang_buttons[code] = button
            seg_layout.addWidget(button, 1)
        self._lang_buttons["th"].setChecked(True)
        grid.addWidget(seg, 1, 0)

        self._model_combo = QComboBox()
        for size, note in MODELS:
            self._model_combo.addItem(f"{size} · {note}", size)
        self._model_combo.setCurrentIndex(self._model_combo.findData(DEFAULT_MODEL))
        grid.addWidget(self._model_combo, 1, 1)
        grid.addWidget(
            _label("ครั้งแรกที่ใช้โมเดลแต่ละขนาด ต้องดาวน์โหลดโมเดลจากอินเทอร์เน็ต", "hint", wrap=True),
            2, 1,
        )
        return card

    def _build_preview_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.addWidget(_label("ตัวอย่างผลถอดความ", "fieldLabel"))
        header.addStretch(1)
        self._chip = _label("", "chip")
        header.addWidget(self._chip)
        layout.addLayout(header)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["#", "เวลา", "ข้อความ"])
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setShowGrid(False)
        self._table.setWordWrap(True)
        self._table.setMinimumHeight(160)
        head = self._table.horizontalHeader()
        head.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        head.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        head.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        head.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._table, 1)

        self._empty = _label(
            "ยังไม่มีผลถอดความ เลือกไฟล์แล้วกด “ถอดเสียงด้วย AI” "
            "ผลลัพธ์จะแสดงที่นี่เมื่อถอดเสียงเสร็จ",
            "empty", wrap=True,
        )
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty, 1)
        return card

    # ---- file selection and submit --------------------------------------

    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "เลือกไฟล์เสียงหรือวิดีโอ", self._last_dir, MEDIA_FILTER
        )
        if path:
            self.set_input_file(path)

    def set_input_file(self, path: str) -> None:
        source = Path(path)
        self._input_path = str(source)
        self._last_dir = str(source.parent)
        kind = "วิดีโอ" if source.suffix.lower() in VIDEO_SUFFIXES else "เสียง"
        try:
            size_text = _format_size(source.stat().st_size)
        except OSError:
            size_text = ""
        self._file_name.setText(source.name)
        self._file_name.setToolTip(str(source))
        self._file_meta.setText(f"{kind} · {source.suffix.lstrip('.').upper() or 'ไม่ทราบชนิด'}")
        self._file_size.setText(size_text)
        self._thumb.setText("▶" if kind == "วิดีโอ" else "♪")
        self._submit_btn.setEnabled(True)
        self._set_status("")

    def selected_language(self) -> str:
        return next(code for code, button in self._lang_buttons.items() if button.isChecked())

    def selected_model(self) -> str:
        return self._model_combo.currentData()

    def _submit(self) -> None:
        if self._input_path is None:
            return
        source = Path(self._input_path)
        task = SubtitleTask(
            str(source),
            str(source.with_suffix(".srt")),
            language=self.selected_language(),
            model_size=self.selected_model(),
            write_file=False,  # the preview is shown first; the user exports from here
        )
        self._task = task
        self._set_status("เพิ่มงานถอดเสียงลงคิวแล้ว ตัวอย่างผลถอดความจะแสดงเมื่อเสร็จ")
        self.task_submitted.emit(task)

    # ---- preview and export ---------------------------------------------

    def show_preview(self, task: SubtitleTask) -> None:
        """Hook for MainWindow: call when a SubtitleTask has finished. Lists task.cues and enables export."""
        self._preview_task = task
        self._cues = tuple(cue for cue in task.cues if cue.text.strip())
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self._table.setRowCount(len(self._cues))
        for row, cue in enumerate(self._cues):
            number = QTableWidgetItem(str(row + 1))
            number.setForeground(QColor("#6d6a66"))
            number.setFont(mono)
            when = QTableWidgetItem(f"{format_srt_time(cue.start)} → {format_srt_time(cue.end)}")
            when.setForeground(QColor("#ff9147"))
            when.setFont(mono)
            for column, item in enumerate((number, when, QTableWidgetItem(cue.text))):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(row, column, item)
        self._refresh_preview_state()
        self._set_status("" if self._cues else "ไม่พบเสียงพูดในไฟล์นี้")

    def _refresh_preview_state(self) -> None:
        has_cues = bool(self._cues)
        if has_cues:
            self._set_chip(f"{len(self._cues)} ประโยค · ซิงก์แล้ว", on=True)
        elif self._preview_task is not None:
            self._set_chip("0 ประโยค", on=False)
        else:
            self._set_chip("รอผลถอดความ", on=False)
        self._table.setVisible(has_cues)
        self._empty.setVisible(not has_cues)
        if self._preview_task is not None and not has_cues:
            self._empty.setText("ไม่พบเสียงพูดในไฟล์นี้ ลองเลือกภาษาหรือไฟล์อื่น")
        self._export_srt_btn.setEnabled(has_cues)
        self._export_vtt_btn.setEnabled(has_cues)

    def _set_chip(self, text: str, on: bool) -> None:
        self._chip.setText(text)
        self._chip.setProperty("on", "true" if on else "false")
        self._chip.style().unpolish(self._chip)
        self._chip.style().polish(self._chip)

    def _suggest_path(self, suffix: str) -> str:
        if self._preview_task is not None:
            return str(Path(self._preview_task.output_path).with_suffix(suffix))
        return str(Path(self._last_dir) / f"subtitle{suffix}")

    def _export(self, suffix: str) -> None:
        if not self._cues:
            return
        file_filter = "SubRip (*.srt)" if suffix == ".srt" else "WebVTT (*.vtt)"
        chosen, _ = QFileDialog.getSaveFileName(
            self, f"ส่งออก {suffix}", self._suggest_path(suffix), file_filter
        )
        if not chosen:
            return
        if not chosen.lower().endswith(suffix):
            chosen += suffix
        try:
            saved = write_subtitles(self._cues, chosen)
        except ClipHubError as exc:
            QMessageBox.warning(self, "ส่งออกไม่สำเร็จ", str(exc))
            return
        self._set_status(f"บันทึกไฟล์แล้ว: {saved}")

    def _set_status(self, text: str) -> None:
        self._status.setText(text)
        self._status.setVisible(bool(text))

