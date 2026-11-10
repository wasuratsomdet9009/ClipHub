from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import ClassVar

from core.errors import InputError, TaskCancelledError

ProgressCallback = Callable[[int, str], None]


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BaseMediaTask(ABC):
    kind: ClassVar[str] = "generic"  # download | convert | compress | subtitle
    title: ClassVar[str] = "งานสื่อ"

    def __init__(self, input_path: str, output_path: str) -> None:
        self.input_path = input_path
        self.output_path = output_path
        self._status = TaskStatus.PENDING
        self._progress = 0
        self._cancel_event = threading.Event()
        self._progress_callback: ProgressCallback | None = None
        self._temp_files: list[Path] = []

    @property
    def status(self) -> TaskStatus:
        return self._status

    def get_progress(self) -> int:
        return self._progress

    def cancel_task(self) -> None:
        self._cancel_event.set()

    def set_progress_callback(self, callback: ProgressCallback | None) -> None:
        self._progress_callback = callback

    def summary(self) -> str:
        """One-line text for the queue row, e.g. 'กำลังบีบอัด · Balanced'."""
        return ""

    def run(self) -> Path:
        self._status = TaskStatus.RUNNING
        try:
            self.validate()
            self.check_cancelled()
            output = self.process()
        except TaskCancelledError:
            self._status = TaskStatus.CANCELLED
            raise
        except Exception:
            self._status = TaskStatus.FAILED
            raise
        else:
            self._status = TaskStatus.DONE
            self.report_progress(100, "เสร็จสิ้น")
            return output
        finally:
            self.cleanup()

    def validate(self) -> None:
        """Hook. Override when the input is not a local file (e.g. a URL)."""
        if not Path(self.input_path).is_file():
            raise InputError(f"ไม่พบไฟล์ต้นทาง: {self.input_path}")

    @abstractmethod
    def process(self) -> Path:
        """Do the work and return the final output path."""

    def is_cancel_requested(self) -> bool:
        """Non-raising check, for loops and for run_ffmpeg(is_cancelled=...)."""
        return self._cancel_event.is_set()

    def check_cancelled(self) -> None:
        if self.is_cancel_requested():
            raise TaskCancelledError("ยกเลิกงานแล้ว")

    def report_progress(self, percent: float, message: str = "") -> None:
        self._progress = max(0, min(100, int(percent)))
        if self._progress_callback is not None:
            self._progress_callback(self._progress, message)

    def partial_output(self) -> Path:
        """Temp name next to the final output. Write here, then os.replace() on success."""
        final = Path(self.output_path)
        return self.register_temp(final.with_name(final.name + ".part"))

    def register_temp(self, path: Path) -> Path:
        self._temp_files.append(Path(path))
        return Path(path)

    def cleanup(self) -> None:
        for path in self._temp_files:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass  # cleanup must never hide the real result
        self._temp_files.clear()
