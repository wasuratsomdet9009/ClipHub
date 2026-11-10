"""Tests for the BaseMediaTask template: lifecycle, cancel, progress and temp-file cleanup."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.base_task import BaseMediaTask, TaskStatus
from core.errors import InputError, TaskCancelledError


class _Task(BaseMediaTask):
    """Smallest useful subclass: writes the partial file, then publishes it."""

    kind = "test"

    def __init__(self, input_path: str, output_path: str, fail: bool = False) -> None:
        super().__init__(input_path, output_path)
        self.fail = fail
        self.process_called = False
        self.partial: Path | None = None

    def process(self) -> Path:
        self.process_called = True
        self.partial = self.partial_output()
        self.partial.write_text("data", encoding="utf-8")
        self.report_progress(50, "ครึ่งทาง")
        if self.fail:
            raise RuntimeError("boom")
        self.check_cancelled()
        self.partial.replace(self.output_path)
        return Path(self.output_path)


class BaseMediaTaskTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.source = self.dir / "in.bin"
        self.source.write_bytes(b"source")
        self.output = self.dir / "out.bin"

    def make(self, **kwargs) -> _Task:
        return _Task(str(self.source), str(self.output), **kwargs)

    def test_initial_state(self) -> None:
        task = self.make()
        self.assertEqual(task.status, TaskStatus.PENDING)
        self.assertEqual(task.get_progress(), 0)
        self.assertFalse(task.is_cancel_requested())
        self.assertEqual(task.summary(), "")

    def test_done(self) -> None:
        task = self.make()
        seen: list[tuple[int, str]] = []
        task.set_progress_callback(lambda percent, message: seen.append((percent, message)))

        result = task.run()

        self.assertEqual(result, self.output)
        self.assertTrue(self.output.is_file())
        self.assertEqual(task.status, TaskStatus.DONE)
        self.assertEqual(task.get_progress(), 100)
        self.assertEqual(seen[0], (50, "ครึ่งทาง"))
        self.assertEqual(seen[-1][0], 100)
        self.assertFalse(task.partial.exists(), "temp file must be gone")
        self.assertEqual([p.name for p in self.dir.iterdir() if p.suffix == ".part"], [])

    def test_failed_reraises_and_cleans_up(self) -> None:
        task = self.make(fail=True)
        with self.assertRaisesRegex(RuntimeError, "boom"):
            task.run()
        self.assertEqual(task.status, TaskStatus.FAILED)
        self.assertNotEqual(task.get_progress(), 100)
        self.assertFalse(task.partial.exists())
        self.assertFalse(self.output.exists())

    def test_cancel_before_run(self) -> None:
        task = self.make()
        task.cancel_task()
        self.assertTrue(task.is_cancel_requested())
        with self.assertRaises(TaskCancelledError):
            task.run()
        self.assertEqual(task.status, TaskStatus.CANCELLED)
        self.assertFalse(task.process_called)

    def test_cancel_during_process_cleans_up(self) -> None:
        task = self.make()
        task.set_progress_callback(lambda percent, message: task.cancel_task())
        with self.assertRaises(TaskCancelledError):
            task.run()
        self.assertEqual(task.status, TaskStatus.CANCELLED)
        self.assertFalse(task.partial.exists())
        self.assertFalse(self.output.exists())

    def test_validate_missing_input(self) -> None:
        task = _Task(str(self.dir / "missing.bin"), str(self.output))
        with self.assertRaises(InputError) as ctx:
            task.run()
        self.assertIn("ไม่พบไฟล์ต้นทาง", str(ctx.exception))
        self.assertEqual(task.status, TaskStatus.FAILED)
        self.assertFalse(task.process_called)

    def test_report_progress_clamps(self) -> None:
        task = self.make()
        seen: list[int] = []
        task.set_progress_callback(lambda percent, message: seen.append(percent))
        for value in (-5, 0, 49.9, 100, 150):
            task.report_progress(value)
        self.assertEqual(seen, [0, 0, 49, 100, 100])
        self.assertEqual(task.get_progress(), 100)

    def test_report_progress_without_callback(self) -> None:
        task = self.make()
        task.report_progress(30, "x")
        self.assertEqual(task.get_progress(), 30)

    def test_partial_output_is_part_file_removed_by_cleanup(self) -> None:
        task = self.make()
        partial = task.partial_output()
        self.assertTrue(partial.name.endswith(".part"))
        self.assertEqual(partial.parent, self.output.parent)
        self.assertEqual(partial.name, self.output.name + ".part")
        partial.write_text("half", encoding="utf-8")
        extra = task.register_temp(self.dir / "scratch.tmp")
        extra.write_text("x", encoding="utf-8")

        task.cleanup()

        self.assertFalse(partial.exists())
        self.assertFalse(extra.exists())
        task.cleanup()  # a second call is harmless

    def test_cleanup_never_raises(self) -> None:
        task = self.make()
        task.partial_output()
        with mock.patch.object(Path, "unlink", side_effect=OSError("locked")):
            task.cleanup()


if __name__ == "__main__":
    unittest.main()
