"""Task queue rail: job cards with progress, cancel and completion alerts (owner: member 1)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.base_task import BaseMediaTask
from core.task_queue import TaskQueue
from ui.theme import ACCENT, INFO, OK, TEXT_2, make_icon, repolish

STATUS_TEXT = {
    "pending": "รอในคิว",
    "running": "กำลังประมวลผล",
    "done": "เสร็จแล้ว",
    "failed": "ผิดพลาด",
    "cancelled": "ยกเลิกแล้ว",
}
FINISHED_STATES = {"done", "failed", "cancelled"}
KIND_COLORS = {"download": INFO, "subtitle": "#a78bfa"}


class _ElidedLabel(QLabel):
    """Single-line label that shows an ellipsis instead of widening the rail."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._full = ""
        self.setText(text)

    def setText(self, text: str) -> None:
        self._full = text
        self.setToolTip(text)
        self._elide()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        shown = self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideRight, max(self.width() - 2, 0))
        super().setText(shown)


class JobCard(QFrame):
    """One row of the queue: icon, title, summary, progress bar, status and cancel button."""

    def __init__(self, task: BaseMediaTask, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("JobCard")
        self.task = task
        self.state = ""
        self.cancelling = False
        self.kind = getattr(task, "kind", "generic")
        kind = self.kind

        self.icon_label = QLabel()
        self.icon_label.setObjectName("JobIcon")
        self.icon_label.setProperty("kind", kind)
        self.icon_label.setFixedSize(34, 34)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setPixmap(make_icon(kind, KIND_COLORS.get(kind, ACCENT), 18).pixmap(18, 18))

        name = getattr(task, "display_name", "") or task.title
        self.title_label = _ElidedLabel(name)
        self.title_label.setObjectName("JobTitle")
        self.summary_label = _ElidedLabel(task.summary())
        self.summary_label.setObjectName("JobSummary")

        self.cancel_button = QPushButton()
        self.cancel_button.setObjectName("JobCancel")
        self.cancel_button.setIcon(make_icon("close", TEXT_2, 13, 2.0))
        self.cancel_button.setFixedSize(26, 26)
        self.cancel_button.setToolTip("ยกเลิกงาน")
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.setProperty("kind", kind)

        self.status_label = _ElidedLabel()
        self.status_label.setObjectName("JobStatus")
        self.percent_label = QLabel("0%")
        self.percent_label.setObjectName("JobPercent")

        meta = QVBoxLayout()
        meta.setSpacing(1)
        meta.addWidget(self.title_label)
        meta.addWidget(self.summary_label)
        top = QHBoxLayout()
        top.setSpacing(11)
        top.addWidget(self.icon_label)
        top.addLayout(meta, 1)
        top.addWidget(self.cancel_button, 0, Qt.AlignmentFlag.AlignTop)
        bottom = QHBoxLayout()
        bottom.addWidget(self.status_label, 1)
        bottom.addWidget(self.percent_label)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(10)
        layout.addLayout(top)
        layout.addWidget(self.progress)
        layout.addLayout(bottom)
        self.set_state("pending")

    def is_finished(self) -> bool:
        return self.state in FINISHED_STATES

    def set_state(self, state: str, detail: str = "") -> None:
        changed = state != self.state
        self.state = state
        text = STATUS_TEXT[state]
        self.status_label.setText(f"{text} · {detail}" if detail else text)
        if not changed:
            return
        self.setProperty("state", state)
        self.icon_label.setProperty("state", state)
        self.cancel_button.setVisible(state not in FINISHED_STATES)
        if state == "done":
            self.progress.setValue(100)
            self.percent_label.setText("100%")
            self.icon_label.setPixmap(make_icon("check", OK, 18, 2.2).pixmap(18, 18))
        for widget in (self, self.icon_label, self.progress):
            repolish(widget)

    def set_progress(self, percent: int, message: str = "") -> None:
        if self.is_finished() or self.cancelling:
            return
        self.progress.setValue(percent)
        self.percent_label.setText(f"{percent}%")
        self.set_state("running", message)

    def mark_cancelling(self) -> None:
        self.cancelling = True
        self.cancel_button.setEnabled(False)
        self.status_label.setText("กำลังยกเลิก…")


class QueuePanel(QWidget):
    def __init__(self, queue: TaskQueue, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.queue = queue
        self.alerts_enabled = True  # tests switch this off to avoid dialogs
        self._cards: dict[BaseMediaTask, JobCard] = {}
        self.setObjectName("Rail")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        queue_icon = QLabel()
        queue_icon.setPixmap(make_icon("queue", ACCENT, 17).pixmap(17, 17))
        title = QLabel("คิวงาน")
        title.setObjectName("RailTitle")
        self.count_badge = QLabel("0 งาน")
        self.count_badge.setObjectName("CountBadge")
        head = QHBoxLayout()
        head.setSpacing(9)
        head.addWidget(queue_icon)
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(self.count_badge)

        self.empty_label = QLabel("ยังไม่มีงานในคิว")
        self.empty_label.setObjectName("RailEmpty")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.jobs_layout = QVBoxLayout()
        self.jobs_layout.setContentsMargins(0, 0, 4, 0)
        self.jobs_layout.setSpacing(12)
        self.jobs_layout.addWidget(self.empty_label)
        self.jobs_layout.addStretch(1)
        holder = QWidget()
        holder.setLayout(self.jobs_layout)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(holder)
        scroll.viewport().setAutoFillBackground(False)
        holder.setAutoFillBackground(False)

        foot = QLabel("UI ไม่ค้างขณะประมวลผล — ทำงานเบื้องหลังด้วย QThread")
        foot.setObjectName("RailFoot")
        foot.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 12, 16)
        layout.setSpacing(16)
        layout.addLayout(head)
        layout.addWidget(scroll, 1)
        layout.addWidget(foot)

        queue.task_added.connect(self._on_added)
        queue.task_started.connect(self._on_started)
        queue.task_progress.connect(self._on_progress)
        queue.task_done.connect(self._on_done)
        queue.task_failed.connect(self._on_failed)
        queue.task_cancelled.connect(self._on_cancelled)

    def unfinished_tasks(self) -> list[BaseMediaTask]:
        return [task for task, card in self._cards.items() if not card.is_finished()]

    def card_for(self, task: BaseMediaTask) -> JobCard | None:
        return self._cards.get(task)

    def _update_count(self) -> None:
        self.count_badge.setText(f"{len(self.unfinished_tasks())} งาน")

    def _on_added(self, task: BaseMediaTask) -> None:
        card = JobCard(task)
        card.cancel_button.clicked.connect(lambda: self._cancel(task))
        self._cards[task] = card
        self.jobs_layout.insertWidget(self.jobs_layout.count() - 1, card)  # before the trailing stretch
        self.empty_label.hide()
        self._update_count()

    def _cancel(self, task: BaseMediaTask) -> None:
        card = self._cards.get(task)
        if card is None or card.is_finished():
            return
        if card.state == "running":
            card.mark_cancelling()  # the worker confirms through task_cancelled
        self.queue.cancel(task)

    def _on_started(self, task: BaseMediaTask) -> None:
        card = self._cards.get(task)
        if card is not None:
            card.set_state("running")

    def _on_progress(self, task: BaseMediaTask, percent: int, message: str) -> None:
        card = self._cards.get(task)
        if card is not None:
            card.set_progress(percent, message)

    def _on_done(self, task: BaseMediaTask, output: object) -> None:
        card = self._cards.get(task)
        if card is not None:
            card.set_state("done")
        self._update_count()
        name = getattr(task, "display_name", "") or task.title
        parts = [name, "เสร็จเรียบร้อยแล้ว"]
        result = getattr(task, "result", None)
        if result is not None:
            parts.append(result.describe())  # compressor: original vs new size (SRS 3.3.2.2)
        if getattr(task, "write_file", True):
            parts.append(f"ไฟล์: {output}")
        else:
            parts.append("ดูตัวอย่างและส่งออกได้ที่หน้าซับไตเติล")
        self._alert(QMessageBox.Icon.Information, "ประมวลผลเสร็จสิ้น", "\n\n".join(parts))

    def _on_failed(self, task: BaseMediaTask, message: str) -> None:
        card = self._cards.get(task)
        if card is not None:
            card.set_state("failed")
            card.status_label.setToolTip(message)
        self._update_count()
        self._alert(QMessageBox.Icon.Warning, "เกิดข้อผิดพลาด", message)

    def _on_cancelled(self, task: BaseMediaTask) -> None:
        card = self._cards.get(task)
        if card is not None:
            card.set_state("cancelled")
        self._update_count()

    def _alert(self, icon: QMessageBox.Icon, title: str, text: str) -> None:
        if not self.alerts_enabled:
            return
        box = QMessageBox(icon, title, text, QMessageBox.StandardButton.Ok, self.window())
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        box.open()  # non-blocking so other jobs keep updating behind the dialog
