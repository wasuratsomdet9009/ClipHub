"""Tests for core.ffmpeg: tool lookup, ffprobe parsing and the ffmpeg runner."""
from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from core import ffmpeg
from core.errors import TaskCancelledError, ToolFailedError, ToolNotFoundError


class FindToolTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        patcher = mock.patch.object(ffmpeg, "_bundle_root", return_value=self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_missing_tool_raises(self) -> None:
        with mock.patch("core.ffmpeg.shutil.which", return_value=None), \
                mock.patch.object(ffmpeg, "_EXTRA_DIRS", ()):
            with self.assertRaises(ToolNotFoundError) as ctx:
                ffmpeg.find_tool("ffmpeg")
        self.assertIn("ffmpeg", str(ctx.exception))
        self.assertIn("ไม่พบโปรแกรม", str(ctx.exception))

    def test_falls_back_to_path(self) -> None:
        with mock.patch("core.ffmpeg.shutil.which", return_value="/usr/local/bin/ffprobe"):
            self.assertEqual(ffmpeg.find_tool("ffprobe"), "/usr/local/bin/ffprobe")

    def test_prefers_bundled_copy(self) -> None:
        exe = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
        (self.root / "bin").mkdir()
        bundled = self.root / "bin" / exe
        bundled.write_text("", encoding="utf-8")
        with mock.patch("core.ffmpeg.shutil.which", return_value="/usr/bin/ffmpeg"):
            self.assertEqual(ffmpeg.find_tool("ffmpeg"), str(bundled))


class ProbeTests(unittest.TestCase):
    def test_probe_duration_parses_seconds(self) -> None:
        payload = json.dumps({"format": {"duration": "12.5", "size": "100"}})
        with mock.patch("core.ffmpeg.find_tool", return_value="ffprobe"), \
                mock.patch("core.ffmpeg.subprocess.run",
                           return_value=SimpleNamespace(stdout=payload)):
            self.assertEqual(ffmpeg.probe_duration("x.mp4"), 12.5)

    def test_unreadable_file_raises(self) -> None:
        for stdout in ("", "{}", "not json"):
            with self.subTest(stdout=stdout), \
                    mock.patch("core.ffmpeg.find_tool", return_value="ffprobe"), \
                    mock.patch("core.ffmpeg.subprocess.run",
                               return_value=SimpleNamespace(stdout=stdout)):
                with self.assertRaises(ToolFailedError):
                    ffmpeg.probe_duration("x.mp4")

    def test_missing_or_zero_duration_raises(self) -> None:
        for duration in ("N/A", "0", "0.0"):
            payload = json.dumps({"format": {"duration": duration}})
            with self.subTest(duration=duration), \
                    mock.patch("core.ffmpeg.find_tool", return_value="ffprobe"), \
                    mock.patch("core.ffmpeg.subprocess.run",
                               return_value=SimpleNamespace(stdout=payload)):
                with self.assertRaisesRegex(ToolFailedError, "ไม่พบความยาว"):
                    ffmpeg.probe_duration("x.mp4")


class _FakeProc:
    def __init__(self, stdout: str, stderr: str = "", returncode: int = 0) -> None:
        self.stdout = io.StringIO(stdout)
        self.stderr = io.StringIO(stderr)
        self._final = returncode
        self.returncode: int | None = None
        self.killed = False

    def poll(self) -> int | None:
        return self.returncode

    def wait(self) -> int:
        if self.returncode is None:
            self.returncode = self._final
        return self.returncode

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


class RunFfmpegTests(unittest.TestCase):
    def run_with(self, proc: _FakeProc, **kwargs):
        with mock.patch("core.ffmpeg.find_tool", return_value="ffmpeg"), \
                mock.patch("core.ffmpeg.subprocess.Popen", return_value=proc) as popen:
            ffmpeg.run_ffmpeg(["-i", "in.mp4", "out.mp4"], **kwargs)
        return popen

    def test_reports_progress_as_fraction(self) -> None:
        lines = "out_time_us=N/A\nout_time_us=2500000\nprogress=continue\nout_time_us=10000000\n"
        calls: list[float] = []
        popen = self.run_with(_FakeProc(lines), duration=10.0, on_progress=calls.append)
        self.assertEqual(calls, [0.25, 1.0])
        cmd = popen.call_args.args[0]
        self.assertEqual(cmd[0], "ffmpeg")
        self.assertIn("-nostdin", cmd)
        self.assertEqual(cmd[-2:], ["in.mp4", "out.mp4"])

    def test_old_ffmpeg_out_time_ms_is_microseconds(self) -> None:
        calls: list[float] = []
        self.run_with(_FakeProc("out_time_ms=5000000\n"), duration=10.0, on_progress=calls.append)
        self.assertEqual(calls, [0.5])

    def test_progress_is_clamped(self) -> None:
        calls: list[float] = []
        self.run_with(_FakeProc("out_time_us=99000000\n"), duration=10.0, on_progress=calls.append)
        self.assertEqual(calls, [1.0])

    def test_failure_carries_last_error_line(self) -> None:
        proc = _FakeProc("", stderr="first\nInvalid data found\n", returncode=1)
        with self.assertRaises(ToolFailedError) as ctx:
            self.run_with(proc, duration=10.0)
        self.assertIn("Invalid data found", str(ctx.exception))
        self.assertIn("first", ctx.exception.stderr)

    def test_cancel_kills_process(self) -> None:
        proc = _FakeProc("out_time_us=1000000\nout_time_us=2000000\n")
        with self.assertRaises(TaskCancelledError):
            self.run_with(proc, duration=10.0, is_cancelled=lambda: True)
        self.assertTrue(proc.killed)

    def test_tool_missing_propagates(self) -> None:
        with mock.patch("core.ffmpeg.shutil.which", return_value=None), \
                mock.patch.object(ffmpeg, "_EXTRA_DIRS", ()), \
                mock.patch.object(ffmpeg, "_bundle_root", return_value=Path("/nonexistent")):
            with self.assertRaises(ToolNotFoundError):
                ffmpeg.run_ffmpeg(["-i", "a", "b"], duration=1.0)


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg not installed")
class RealFfmpegTests(unittest.TestCase):
    def test_sine_to_mp4(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "sine.wav"
            ffmpeg.run_ffmpeg(
                ["-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                 "-c:a", "pcm_s16le", "-f", "wav", str(wav)],
                duration=1.0,
            )
            self.assertTrue(wav.is_file())
            self.assertAlmostEqual(ffmpeg.probe_duration(str(wav)), 1.0, delta=0.2)

            out = Path(tmp) / "sine.mp4.part"  # .part name: muxer must be explicit
            calls: list[float] = []
            ffmpeg.run_ffmpeg(
                ["-i", str(wav), "-c:a", "aac", "-f", "mp4", str(out)],
                duration=ffmpeg.probe_duration(str(wav)),
                on_progress=calls.append,
            )
            self.assertTrue(out.is_file())
            self.assertGreater(out.stat().st_size, 0)
            self.assertTrue(calls, "on_progress was never called")
            self.assertTrue(all(0.0 <= value <= 1.0 for value in calls))

    def test_bad_input_raises_tool_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.mp4"
            bad.write_bytes(b"not a video")
            with self.assertRaises(ToolFailedError):
                ffmpeg.run_ffmpeg(
                    ["-i", str(bad), "-f", "mp4", str(Path(tmp) / "o.part")], duration=1.0
                )


if __name__ == "__main__":
    unittest.main()
