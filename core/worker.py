"""QThread wrapper that runs one BaseMediaTask off the UI thread."""
from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from core.base_task import BaseMediaTask
from core.errors import ClipHubError, TaskCancelledError


class TaskWorker(QThread):
    progress = Signal(int, str)   # percent, message
    finished_ok = Signal(object)  # output Path
    failed = Signal(str)          # message shown to the user
    cancelled = Signal()

    def __init__(self, task: BaseMediaTask, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.task = task
        task.set_progress_callback(self._emit_progress)

    def _emit_progress(self, percent: int, message: str) -> None:
        self.progress.emit(percent, message)

    def cancel(self) -> None:
        self.task.cancel_task()

    def run(self) -> None:
        try:
            output = self.task.run()
        except TaskCancelledError:
            self.cancelled.emit()
        except ClipHubError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # keep the app alive on unexpected errors
            self.failed.emit(f"เกิดข้อผิดพลาดไม่คาดคิด: {exc}")
        else:
            self.finished_ok.emit(output)
