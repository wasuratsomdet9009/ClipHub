"""Feature 3 page: compressor UI with live size estimate (owner: member 3)."""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QRegularExpression, Qt, QThread, Signal
from PySide6.QtGui import QColor, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFileDialog, QFrame, QGraphicsDropShadowEffect,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from core.errors import ClipHubError
from core.ffmpeg import probe_duration
from tasks.compressor import (
    CUSTOM_MODE, PRESET_LABELS, PRESETS, CompressTask, estimate_output_bytes,
    format_size, original_kbps, suggest_output_path,
)

VIDEO_FILTER = "วิดีโอ (*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.flv *.wmv *.ts);;ทุกไฟล์ (*)"
DEFAULT_CUSTOM_KBPS = "6000"
PRESET_HINTS = {
    "high": "คุณภาพใกล้เคียงต้นฉบับ ลดขนาดเล็กน้อย",
    "balanced": "สมดุลระหว่างคุณภาพกับขนาด · เหมาะกับการอัปโหลดโซเชียล",
    "small": "ไฟล์เล็กที่สุด ภาพอาจคมชัดน้อยลง",
}
MODE_IDS = {0: "high", 1: "balanced", 2: "small", 3: CUSTOM_MODE}

# Colors are the :root tokens of cliphub-mockup.html (rgba alpha is 0-255 in Qt).
MONO = '"IBM Plex Mono", "SF Mono", Menlo, Consolas, monospace'
STYLE = f"""
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QLabel {{ color: #f4f3f2; background: transparent; }}
QLabel#pageTitle {{ font-size: 26px; font-weight: 700; }}
QLabel#pageDesc {{ font-size: 14px; color: #a6a29c; }}
QLabel#badge {{ font-size: 12px; color: #a6a29c; padding: 7px 13px; border-radius: 16px;
  background: rgba(28,28,30,148); border: 1px solid rgba(255,255,255,26); }}
QFrame#card {{ background: rgba(28,28,30,148); border: 1px solid rgba(255,255,255,26); border-radius: 16px; }}
QLabel#fieldLabel {{ font-size: 11px; font-weight: 600; color: #a6a29c; }}
QLabel#thumb {{ font-size: 16px; color: #6d6a66; border-radius: 8px;
  background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #2a2a2d, stop:1 #1b1b1d); }}
QLabel#fileName {{ font-size: 14px; font-weight: 600; }}
QLabel#fileMeta {{ font-family: {MONO}; font-size: 12px; color: #6d6a66; }}
QLabel#fileMeta[error="true"] {{ color: #f87171; }}
QLabel#fileSize {{ font-family: {MONO}; font-size: 13px; color: #a6a29c; }}
QPushButton#ghostButton {{ color: #f4f3f2; font-size: 13px; padding: 9px 15px; border-radius: 12px;
  background: rgba(34,34,37,184); border: 1px solid rgba(255,255,255,41); }}
QPushButton#ghostButton:hover {{ background: rgba(255,255,255,20); }}
QFrame#segBar {{ background: rgba(10,10,11,153); border: 1px solid rgba(255,255,255,26); border-radius: 12px; }}
QPushButton#segButton {{ color: #a6a29c; font-size: 14px; padding: 9px 10px; border-radius: 8px;
  background: transparent; border: 1px solid transparent; }}
QPushButton#segButton:hover {{ color: #f4f3f2; }}
QPushButton#segButton:checked {{ color: #f4f3f2; background: #2e2e30; border: 1px solid rgba(255,255,255,41); }}
QFrame#control {{ background: rgba(10,10,11,166); border: 1px solid rgba(255,255,255,26); border-radius: 12px; }}
QFrame#control[active="true"] {{ border: 1px solid rgba(255,122,26,107); }}
QLineEdit#kbpsEdit {{ background: transparent; border: none; color: #f4f3f2; font-family: {MONO};
  font-size: 14px; selection-background-color: #ff7a1a; selection-color: #1a0f04; }}
QLabel#unit {{ font-family: {MONO}; font-size: 13px; color: #6d6a66; }}
QLabel#note {{ font-size: 12px; color: #6d6a66; }}
QLabel#barLabel {{ font-size: 13px; color: #a6a29c; }}
QLabel#barAmount {{ font-family: {MONO}; font-size: 13px; }}
QLabel#barAmount[accent="true"] {{ color: #ff9147; }}
QProgressBar {{ background: rgba(255,255,255,15); border: none; border-radius: 7px; min-height: 14px; max-height: 14px; }}
QProgressBar::chunk {{ border-radius: 7px; }}
QProgressBar#barOrig::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #5a5a5d, stop:1 #3a3a3d); }}
QProgressBar#barNew::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #ff9147, stop:1 #ff7a1a); }}
QFrame#saving {{ border-radius: 12px; }}
QFrame#saving[state="idle"] {{ background: rgba(255,255,255,8); border: 1px solid rgba(255,255,255,26); }}
QFrame#saving[state="ok"] {{ background: rgba(52,211,153,36); border: 1px solid rgba(52,211,153,77); }}
QFrame#saving[state="warn"] {{ background: rgba(251,146,60,36); border: 1px solid rgba(251,146,60,77); }}
QLabel#savingBig {{ font-family: {MONO}; font-size: 30px; font-weight: 600; color: #6d6a66; }}
QLabel#savingBig[state="ok"] {{ color: #34d399; }}
QLabel#savingBig[state="warn"] {{ color: #fb923c; }}
QLabel#savingTitle {{ font-size: 14px; font-weight: 600; }}
QLabel#savingSub {{ font-size: 12px; color: #a6a29c; }}
QPushButton#primaryButton {{ color: #1a0f04; font-size: 14px; font-weight: 600; padding: 0 20px; min-height: 48px;
  border-radius: 12px; border: 1px solid transparent;
  background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ff9147, stop:1 #ff7a1a); }}
QPushButton#primaryButton:hover {{ background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffa263, stop:1 #ff8a33); }}
QPushButton#primaryButton:pressed {{ background: #e85f00; }}
QPushButton#primaryButton:disabled {{ color: #6d6a66; background: rgba(255,255,255,20); }}
QLabel#footHint {{ font-family: {MONO}; font-size: 12px; color: #6d6a66; }}
"""


def _set_prop(widget: QWidget, name: str, value: object) -> None:
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _format_duration(seconds: float) -> str:
    minutes, secs = divmod(int(round(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def _format_kbps(kbps: float) -> str:
    return f"{kbps / 1000:.1f} Mbps" if kbps >= 1000 else f"{kbps:.0f} kbps"


class _ProbeWorker(QThread):
    """Reads size and duration off the GUI thread (ffprobe can take a moment)."""

    probed = Signal(str, int, float)  # path, size in bytes, duration in seconds
    failed = Signal(str, str)         # path, Thai message

    def __init__(self, path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.path = path

    def run(self) -> None:
        try:
            size = os.path.getsize(self.path)
            duration = probe_duration(self.path)
        except ClipHubError as exc:
            self.failed.emit(self.path, str(exc))
        except OSError as exc:
            self.failed.emit(self.path, f"อ่านไฟล์ไม่ได้: {exc}")
        else:
            self.probed.emit(self.path, size, duration)


class _KbpsEdit(QLineEdit):
    activated = Signal()  # focus in: the user is about to type a custom bitrate

    def focusInEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().focusInEvent(event)
        user_reasons = (
            Qt.FocusReason.MouseFocusReason, Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason,
        )
        if event.reason() in user_reasons:  # ignore the initial focus Qt hands out on show
            self.activated.emit()


class CompressorPage(QWidget):
    task_submitted = Signal(object)  # CompressTask

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._path: str | None = None
        self._size = 0
        self._duration = 0.0
        self._probes: set[_ProbeWorker] = set()
        self._reserved: set[str] = set()  # outputs already queued, so names stay unique
        self._last_dir = str(Path.home())
        self._build()
        self._refresh()
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._wait_for_probes)

    # --- layout ---------------------------------------------------------------

    def _build(self) -> None:
        self.setStyleSheet(STYLE)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)
        content = QWidget()
        scroll.setWidget(content)
        col = QVBoxLayout(content)
        col.setContentsMargins(24, 24, 24, 24)
        col.setSpacing(16)

        col.addLayout(self._build_head())
        col.addWidget(self._build_file_card())
        col.addWidget(self._build_mode_card())
        col.addWidget(self._build_estimate_card())
        col.addLayout(self._build_footer())
        col.addStretch(1)

    def _build_head(self) -> QHBoxLayout:
        row = QHBoxLayout()
        text = QVBoxLayout()
        text.setSpacing(6)
        title = QLabel("บีบอัดขนาดไฟล์")
        title.setObjectName("pageTitle")
        desc = QLabel("ลดขนาดวิดีโอด้วย Codec H.264 / AAC เลือกพรีเซ็ตสำเร็จรูปหรือกำหนด Bitrate เอง "
                      "พร้อมประเมินขนาดผลลัพธ์ก่อนประมวลผล")
        desc.setObjectName("pageDesc")
        desc.setWordWrap(True)
        text.addWidget(title)
        text.addWidget(desc)
        badge = QLabel("H.264 · AAC")
        badge.setObjectName("badge")
        row.addLayout(text, 1)
        row.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        return row

    def _card(self) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(10)
        return card, layout

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def _build_file_card(self) -> QFrame:
        card, layout = self._card()
        row = QHBoxLayout()
        row.setSpacing(14)
        thumb = QLabel("▶")
        thumb.setObjectName("thumb")
        thumb.setFixedSize(64, 44)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        meta = QVBoxLayout()
        meta.setSpacing(2)
        self.file_name = QLabel("ยังไม่ได้เลือกไฟล์")
        self.file_name.setObjectName("fileName")
        self.file_meta = QLabel("เลือกวิดีโอที่ต้องการบีบอัด")
        self.file_meta.setObjectName("fileMeta")
        for label in (self.file_name, self.file_meta):
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            meta.addWidget(label)
        self.file_size = QLabel("—")
        self.file_size.setObjectName("fileSize")
        self.choose_btn = QPushButton("เลือกไฟล์…")
        self.choose_btn.setObjectName("ghostButton")
        self.choose_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.choose_btn.clicked.connect(self._choose_file)
        row.addWidget(thumb)
        row.addLayout(meta, 1)
        row.addWidget(self.file_size)
        row.addWidget(self.choose_btn)
        layout.addLayout(row)
        return card

    def _build_mode_card(self) -> QFrame:
        card, layout = self._card()
        layout.addWidget(self._field_label("โหมดการบีบอัด"))

        bar = QFrame()
        bar.setObjectName("segBar")
        bar_row = QHBoxLayout(bar)
        bar_row.setContentsMargins(4, 4, 4, 4)
        bar_row.setSpacing(4)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        for button_id, mode in MODE_IDS.items():
            button = QPushButton(bar)
            button.setCheckable(True)
            if mode == CUSTOM_MODE:
                button.hide()  # stands in for "no preset"; checked while the kbps field is in use
            else:
                button.setObjectName("segButton")
                button.setText(f"{PRESET_LABELS[mode]}\n−{round(PRESETS[mode] * 100)}%")
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                bar_row.addWidget(button)
            self.mode_group.addButton(button, button_id)
        self.mode_group.button(1).setChecked(True)
        self.mode_group.idToggled.connect(self._on_mode_toggled)
        layout.addWidget(bar)

        layout.addSpacing(6)
        layout.addWidget(self._field_label("หรือกำหนด Target Bitrate เอง"))
        self.control = QFrame()
        self.control.setObjectName("control")
        self.control.setFixedHeight(54)
        control_row = QHBoxLayout(self.control)
        control_row.setContentsMargins(16, 0, 14, 0)
        self.kbps_edit = _KbpsEdit(DEFAULT_CUSTOM_KBPS)
        self.kbps_edit.setObjectName("kbpsEdit")
        self.kbps_edit.setValidator(QRegularExpressionValidator(QRegularExpression(r"[0-9]{0,6}")))
        self.kbps_edit.setAccessibleName("bitrate")
        self.kbps_edit.activated.connect(self._use_custom)
        self.kbps_edit.textEdited.connect(lambda _text: self._use_custom())
        self.kbps_edit.textChanged.connect(lambda _text: self._refresh())
        unit = QLabel("kbps")
        unit.setObjectName("unit")
        control_row.addWidget(self.kbps_edit, 1)
        control_row.addWidget(unit)
        layout.addWidget(self.control)
        note = QLabel("นับรวมเสียง AAC · ใช้แทนพรีเซ็ตเมื่อคลิกหรือพิมพ์ในช่องนี้")
        note.setObjectName("note")
        layout.addWidget(note)
        return card

    def _build_estimate_card(self) -> QFrame:
        card, layout = self._card()
        layout.addWidget(self._field_label("ประเมินผลลัพธ์"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(16)
        grid.setColumnMinimumWidth(0, 88)
        grid.setColumnMinimumWidth(2, 84)
        self.bar_orig, self.amount_orig = self._bar_row(grid, 0, "ต้นฉบับ", "barOrig", False)
        self.bar_new, self.amount_new = self._bar_row(grid, 1, "หลังบีบอัด", "barNew", True)
        layout.addSpacing(6)
        layout.addLayout(grid)
        layout.addSpacing(6)

        self.saving = QFrame()
        self.saving.setObjectName("saving")
        saving_row = QHBoxLayout(self.saving)
        saving_row.setContentsMargins(16, 16, 16, 16)
        saving_row.setSpacing(14)
        self.saving_big = QLabel("—")
        self.saving_big.setObjectName("savingBig")
        text = QVBoxLayout()
        text.setSpacing(2)
        self.saving_title = QLabel()
        self.saving_title.setObjectName("savingTitle")
        self.saving_sub = QLabel()
        self.saving_sub.setObjectName("savingSub")
        self.saving_sub.setWordWrap(True)
        text.addWidget(self.saving_title)
        text.addWidget(self.saving_sub)
        saving_row.addWidget(self.saving_big)
        saving_row.addLayout(text, 1)
        layout.addWidget(self.saving)
        return card

    def _bar_row(
        self, grid: QGridLayout, row: int, text: str, bar_name: str, accent: bool
    ) -> tuple[QProgressBar, QLabel]:
        label = QLabel(text)
        label.setObjectName("barLabel")
        bar = QProgressBar()
        bar.setObjectName(bar_name)
        bar.setRange(0, 1000)
        bar.setTextVisible(False)
        amount = QLabel("—")
        amount.setObjectName("barAmount")
        amount.setProperty("accent", accent)
        amount.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(label, row, 0)
        grid.addWidget(bar, row, 1)
        grid.addWidget(amount, row, 2)
        return bar, amount

    def _build_footer(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(18)
        self.start_btn = QPushButton("เริ่มบีบอัด")
        self.start_btn.setObjectName("primaryButton")
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.clicked.connect(self._submit)
        self.glow = QGraphicsDropShadowEffect(self.start_btn)
        self.glow.setBlurRadius(26)
        self.glow.setOffset(0, 0)
        self.glow.setColor(QColor(255, 122, 26, 120))
        self.start_btn.setGraphicsEffect(self.glow)
        self.foot_hint = QLabel()
        self.foot_hint.setObjectName("footHint")
        row.addWidget(self.start_btn)
        row.addWidget(self.foot_hint, 1)
        return row

    # --- state ----------------------------------------------------------------

    def _mode(self) -> str:
        return MODE_IDS.get(self.mode_group.checkedId(), "balanced")

    def _custom_kbps(self) -> int | None:
        text = self.kbps_edit.text()
        return int(text) if text.isdigit() and int(text) > 0 else None

    def _use_custom(self) -> None:
        if self._mode() != CUSTOM_MODE:
            self.mode_group.button(3).setChecked(True)

    def _on_mode_toggled(self, _button_id: int, checked: bool) -> None:
        if checked:
            self._refresh()

    def _refresh(self) -> None:
        """Recompute the estimate, saving card and button state from the current inputs."""
        mode = self._mode()
        custom = mode == CUSTOM_MODE
        kbps = self._custom_kbps()
        _set_prop(self.control, "active", custom)

        ready = self._size > 0 and self._duration > 0
        usable = ready and (not custom or kbps is not None)
        self.start_btn.setEnabled(usable)
        self.glow.setEnabled(usable)
        self.bar_orig.setValue(1000 if ready else 0)
        self.amount_orig.setText(format_size(self._size) if ready else "—")

        if not usable:
            self.bar_new.setValue(0)
            self.amount_new.setText("—")
            self._set_saving("idle", "—", "ยังไม่มีข้อมูลประเมิน",
                             "เลือกไฟล์วิดีโอ" if not ready else "กรอก Target Bitrate เป็นตัวเลขมากกว่า 0")
            self.foot_hint.setText("เลือกไฟล์วิดีโอเพื่อเริ่มต้น" if not ready else "")
            return

        estimate = estimate_output_bytes(self._size, self._duration, mode, kbps)
        saved = self._size - estimate
        percent = round(abs(saved) / self._size * 100)
        self.bar_new.setValue(min(1000, round(estimate / self._size * 1000)))
        self.amount_new.setText(format_size(estimate))
        if saved >= 0:
            sub = PRESET_HINTS.get(mode, "ใช้ Target Bitrate ที่กำหนดเอง")
            self._set_saving("ok", f"−{percent}%", f"ประหยัดพื้นที่ {format_size(saved)}", sub)
        else:
            self._set_saving("warn", f"+{percent}%", f"ไฟล์อาจใหญ่ขึ้น {format_size(-saved)}",
                             "Bitrate เป้าหมายสูงกว่าไฟล์ต้นฉบับ ลองลดค่าลง")
        label = f"Custom {kbps} kbps" if custom else f"{PRESET_LABELS[mode]} preset"
        self.foot_hint.setText(f"≈ {format_size(estimate)} · {label}")

    def _set_saving(self, state: str, big: str, title: str, sub: str) -> None:
        _set_prop(self.saving, "state", state)
        _set_prop(self.saving_big, "state", state)
        self.saving_big.setText(big)
        self.saving_title.setText(title)
        self.saving_sub.setText(sub)

    # --- file selection and probing -------------------------------------------

    def _choose_file(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, "เลือกไฟล์วิดีโอ", self._last_dir, VIDEO_FILTER)
        if path:
            self.set_input_file(path)

    def set_input_file(self, path: str) -> None:
        """Select a source file and start reading its size and duration in the background."""
        self._path = path
        self._last_dir = os.path.dirname(path) or self._last_dir
        self._size = 0
        self._duration = 0.0
        self.file_name.setText(os.path.basename(path))
        self.file_name.setToolTip(path)
        self.file_meta.setText("กำลังอ่านข้อมูลไฟล์…")
        _set_prop(self.file_meta, "error", False)
        self.file_size.setText("…")
        self._refresh()

        worker = _ProbeWorker(path, self)
        worker.probed.connect(self._on_probed)
        worker.failed.connect(self._on_probe_failed)
        worker.finished.connect(self._on_probe_finished)
        self._probes.add(worker)
        worker.start()

    def _on_probed(self, path: str, size: int, duration: float) -> None:
        if path != self._path:
            return  # the user already picked another file
        self._size = size
        self._duration = duration
        bitrate = _format_kbps(original_kbps(size, duration))
        self.file_meta.setText(f"{_format_duration(duration)} · {bitrate}")
        self.file_size.setText(format_size(size))
        self._refresh()

    def _on_probe_failed(self, path: str, message: str) -> None:
        if path != self._path:
            return
        self.file_meta.setText(message)
        _set_prop(self.file_meta, "error", True)
        self.file_size.setText("—")
        self._refresh()

    def _on_probe_finished(self) -> None:
        worker = self.sender()
        if isinstance(worker, _ProbeWorker):
            self._probes.discard(worker)
            worker.deleteLater()

    def _wait_for_probes(self) -> None:
        for worker in list(self._probes):
            worker.wait(3000)

    # --- submit ---------------------------------------------------------------

    def _submit(self) -> None:
        if self._path is None or not self.start_btn.isEnabled():
            return
        mode = self._mode()
        output = suggest_output_path(self._path, self._reserved)
        self._reserved.add(str(output))
        task = CompressTask(
            self._path, str(output), mode=mode,
            target_kbps=self._custom_kbps() if mode == CUSTOM_MODE else None,
        )
        self.task_submitted.emit(task)
        self.foot_hint.setText(f"เพิ่มลงคิวแล้ว → {output.name}")

