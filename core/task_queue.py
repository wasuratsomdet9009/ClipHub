"""Serial job queue: runs one BaseMediaTask at a time on a TaskWorker."""
from __future__ import annotations

from collections import deque

from PySide6.QtCore import QObject, Signal

from core.base_task import BaseMediaTask
from core.worker import TaskWorker


class TaskQueue(QObject):
    task_added = Signal(object)               # task
    task_started = Signal(object)             # task
    task_progress = Signal(object, int, str)  # task, percent, message
    task_done = Signal(object, object)        # task, output Path
    task_failed = Signal(object, str)         # task, message
    task_cancelled = Signal(object)           # task

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pending: deque[BaseMediaTask] = deque()
        self._current_task: BaseMediaTask | None = None
        self._current_worker: TaskWorker | None = None

    def enqueue(self, task: BaseMediaTask) -> None:
        self._pending.append(task)
        self.task_added.emit(task)
        self._start_next()

    def cancel(self, task: BaseMediaTask) -> None:
        if task is self._current_task and self._current_worker is not None:
            self._current_worker.cancel()  # task_cancelled fires when the worker returns
        elif task in self._pending:
            self._pending.remove(task)
            self.task_cancelled.emit(task)

    def is_busy(self) -> bool:
        return self._current_worker is not None

    def shutdown(self, timeout_ms: int = 5000) -> None:
        """Drop pending jobs, cancel the running one and wait for its thread. Call on app exit."""
        self._pending.clear()
        worker = self._current_worker
        if worker is not None:
            worker.cancel()
            worker.wait(timeout_ms)

    def _start_next(self) -> None:
        if self._current_worker is not None or not self._pending:
            return
        task = self._pending.popleft()
        worker = TaskWorker(task, self)
        worker.progress.connect(self._on_progress)
        worker.finished_ok.connect(self._on_done)
        worker.failed.connect(self._on_failed)
        worker.cancelled.connect(self._on_cancelled)
        worker.finished.connect(self._on_worker_finished)
        self._current_task = task
        self._current_worker = worker
        self.task_started.emit(task)
        worker.start()

    def _on_progress(self, percent: int, message: str) -> None:
        self.task_progress.emit(self._current_task, percent, message)

    def _on_done(self, output: object) -> None:
        self.task_done.emit(self._current_task, output)

    def _on_failed(self, message: str) -> None:
        self.task_failed.emit(self._current_task, message)

    def _on_cancelled(self) -> None:
        self.task_cancelled.emit(self._current_task)

    def _on_worker_finished(self) -> None:
        worker = self._current_worker
        self._current_task = None
        self._current_worker = None
        if worker is not None:
            worker.wait()  # finished is emitted from the thread itself; let it fully stop first
            worker.deleteLater()
        self._start_next()
