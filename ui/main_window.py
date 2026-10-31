"""Main window: sidebar, feature pages and the task queue rail (owner: member 1)."""
from __future__ import annotations

import time

from PySide6.QtCore import QCoreApplication, QSize, Qt, QThread
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.task_queue import TaskQueue
from tasks.subtitle import SubtitleTask
from ui.pages import PAGES
from ui.pages.subtitle_page import SubtitlePage
from ui.queue_panel import QueuePanel
from ui.theme import ACCENT, TEXT_2, make_icon

SIDEBAR_WIDTH = 248
RAIL_WIDTH = 340
SHUTDOWN_WAIT_SECONDS = 5.0
STILL_STOPPING_TEXT = (
    "งานที่กำลังทำยังหยุดไม่เสร็จ (เช่น กำลังดึงข้อมูลวิดีโอ หรือโหลดโมเดล AI)\n"
    "โปรดรอสักครู่แล้วปิดหน้าต่างอีกครั้ง"
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ClipHUB — Media Toolkit")
        self.setMinimumSize(1060, 700)
        self.resize(1200, 812)
        self.queue = TaskQueue(self)
        self.nav_buttons: list[QPushButton] = []
        self.pages: list[QWidget] = []

        central = QWidget()
        central.setObjectName("Central")
        row = QHBoxLayout(central)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self.nav_group = QButtonGroup(self)
        self.stack = QStackedWidget()
        row.addWidget(self._build_sidebar())
        row.addWidget(self._build_content(), 1)
        self.queue_panel = QueuePanel(self.queue)
        self.queue_panel.setFixedWidth(RAIL_WIDTH)
        row.addWidget(self.queue_panel)
        self.setCentralWidget(central)

        self.nav_group.idClicked.connect(self.stack.setCurrentIndex)
        self.nav_buttons[0].setChecked(True)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(SIDEBAR_WIDTH)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 20, 14, 20)
        layout.setSpacing(4)

        mark = QLabel()
        mark.setObjectName("BrandMark")
        mark.setFixedSize(42, 42)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setPixmap(make_icon("play", "#1a0f04", 22).pixmap(22, 22))
        name = QLabel("ClipHUB")
        name.setObjectName("BrandName")
        version = QLabel("v1.0")
        version.setObjectName("BrandVersion")
        texts = QVBoxLayout()
        texts.setSpacing(2)
        texts.addWidget(name)
        texts.addWidget(version)
        brand = QHBoxLayout()
        brand.setContentsMargins(8, 8, 8, 20)
        brand.setSpacing(12)
        brand.addWidget(mark)
        brand.addLayout(texts)
        brand.addStretch(1)
        layout.addLayout(brand)

        nav_label = QLabel("เครื่องมือ")
        nav_label.setObjectName("NavLabel")
        layout.addWidget(nav_label)
        for index, (label, icon_key, _page_cls) in enumerate(PAGES):
            button = QPushButton(label)
            button.setProperty("nav", True)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setIconSize(QSize(21, 21))
            button.setIcon(make_icon(icon_key, TEXT_2, 21))
            button.toggled.connect(lambda checked, b=button, k=icon_key: b.setIcon(make_icon(k, ACCENT if checked else TEXT_2, 21)))
            self.nav_group.addButton(button, index)
            self.nav_buttons.append(button)
            layout.addWidget(button)
            layout.addSpacing(3)
        layout.addStretch(1)
        return sidebar

    def _build_content(self) -> QScrollArea:
        for _label, _icon_key, page_cls in PAGES:
            page = page_cls()
            page.task_submitted.connect(self.queue.enqueue)
            self.pages.append(page)
            self.stack.addWidget(page)
        self.queue.task_done.connect(self._on_task_done)

        holder = QWidget()  # padding from the mockup's .main (28px 30px 34px) lives here, not in the pages
        holder_layout = QVBoxLayout(holder)
        holder_layout.setContentsMargins(30, 28, 30, 34)
        holder_layout.addWidget(self.stack)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(holder)
        scroll.viewport().setAutoFillBackground(False)
        return scroll

    def _on_task_done(self, task: object, _output: object) -> None:
        """A finished subtitle job shows its cues in the subtitle page, whether or not a file was written."""
        if not isinstance(task, SubtitleTask):
            return
        for page in self.pages:
            if isinstance(page, SubtitlePage):
                page.show_preview(task)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Cancel running work and wait for it. Qt aborts if a live QThread is destroyed, so a close that cannot finish is refused."""
        for task in self.queue_panel.unfinished_tasks():
            self.queue.cancel(task)
        deadline = time.monotonic() + SHUTDOWN_WAIT_SECONDS
        while not self._is_idle() and time.monotonic() < deadline:
            QCoreApplication.processEvents()
            QThread.msleep(20)
        if not self._is_idle():
            event.ignore()
            QMessageBox.information(self, "ยังหยุดงานไม่เสร็จ", STILL_STOPPING_TEXT)
            return
        super().closeEvent(event)

    def _is_idle(self) -> bool:
        """True when no task runs and every page reports its own worker has finished."""
        pages_idle = all(page.shutdown() for page in self.pages if callable(getattr(page, "shutdown", None)))
        return pages_idle and not self.queue.is_busy()
