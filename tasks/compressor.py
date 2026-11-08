"""Unit tests for Feature 3 (tasks/compressor.py). No ffmpeg, network or Qt needed."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.base_task import TaskStatus
from core.errors import InputError, TaskCancelledError, ToolFailedError
from tasks.compressor import (
    PRESETS, CompressReport, CompressTask, build_compress_args, estimate_output_bytes,
    format_size, original_kbps, split_bitrate, suggest_output_path, target_total_kbps,
)

GB = 1_000_000_000


class PresetTests(unittest.TestCase):
    def test_reduction_values_match_srs(self) -> None:
        self.assertEqual(PRESETS, {"high": 0.20, "balanced": 0.50, "small": 0.70})


class BitrateMathTests(unittest.TestCase):
    def test_original_kbps(self) -> None:
        self.assertAlmostEqual(original_kbps(1_000_000, 8), 1000.0)

    def test_zero_duration_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            original_kbps(GB, 0)

    def test_preset_total_is_share_of_original(self) -> None:
        base = original_kbps(GB, 600)
        self.assertAlmostEqual(target_total_kbps(GB, 600, "high"), base * 0.8)
        self.assertAlmostEqual(target_total_kbps(GB, 600, "small"), base * 0.3)

    def test_custom_uses_target_as_total(self) -> None:
        self.assertEqual(target_total_kbps(GB, 600, "custom", 6000), 6000.0)

    def test_custom_requires_positive_target(self) -> None:
        for bad in (None, 0, -5):
            with self.assertRaises(ValueError):
                target_total_kbps(GB, 600, "custom", bad)

    def test_unknown_mode_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            target_total_kbps(GB, 600, "ultra")


class SplitBitrateTests(unittest.TestCase):
    def test_audio_is_subtracted_from_total(self) -> None:
        self.assertEqual(split_bitrate(6000), (5872, 128))

    def test_video_floor_is_200(self) -> None:
        self.assertEqual(split_bitrate(250), (200, 128))
        self.assertEqual(split_bitrate(10), (200, 128))

    def test_custom_audio_bitrate(self) -> None:
        self.assertEqual(split_bitrate(1000, audio_kbps=192), (808, 192))


class EstimateTests(unittest.TestCase):
    def test_one_gb_at_balanced_is_about_half(self) -> None:
        estimate = estimate_output_bytes(GB, 600, "balanced")
        self.assertAlmostEqual(estimate / GB, 0.5, delta=0.01)

    def test_other_presets(self) -> None:
        self.assertAlmostEqual(estimate_output_bytes(GB, 600, "high") / GB, 0.8, delta=0.01)
        self.assertAlmostEqual(estimate_output_bytes(GB, 600, "small") / GB, 0.3, delta=0.01)

    def test_custom_bitrate(self) -> None:
        # 8000 kbps total for 100 s is 100 MB
        self.assertAlmostEqual(estimate_output_bytes(GB, 100, "custom", 8000), 100_000_000, delta=100_000)

    def test_floor_makes_estimate_larger_than_target(self) -> None:
        # 100 kbps total is below audio + video floor (328 kbps), so the estimate uses the floor
        self.assertAlmostEqual(estimate_output_bytes(GB, 100, "custom", 100), 328 * 125 * 100, delta=10)

    def test_format_size(self) -> None:
        self.assertEqual(format_size(1.24e9), "1.24 GB")
        self.assertEqual(format_size(595e6), "595 MB")
        self.assertEqual(format_size(5.2e6), "5.2 MB")
        self.assertEqual(format_size(40_000), "40 KB")


class BuildArgsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.args = build_compress_args("in.mkv", "out.mp4.part", 5000, 128)

    def test_partial_path_is_last(self) -> None:
        self.assertEqual(self.args[-1], "out.mp4.part")

    def test_muxer_is_explicit(self) -> None:
        i = self.args.index("-f")
        self.assertEqual(self.args[i + 1], "mp4")
        self.assertLess(i, len(self.args) - 1)

    def test_video_rate_control(self) -> None:
        self.assertEqual(self.args[self.args.index("-b:v") + 1], "5000k")
        self.assertEqual(self.args[self.args.index("-maxrate") + 1], "5000k")
        self.assertEqual(self.args[self.args.index("-bufsize") + 1], "10000k")

    def test_codecs_and_flags(self) -> None:
        self.assertEqual(self.args[self.args.index("-c:v") + 1], "libx264")
        self.assertEqual(self.args[self.args.index("-preset") + 1], "medium")
        self.assertEqual(self.args[self.args.index("-pix_fmt") + 1], "yuv420p")
        self.assertEqual(self.args[self.args.index("-c:a") + 1], "aac")
        self.assertEqual(self.args[self.args.index("-b:a") + 1], "128k")
        self.assertEqual(self.args[self.args.index("-movflags") + 1], "+faststart")

    def test_input_comes_first(self) -> None:
        self.assertEqual(self.args[:2], ["-i", "in.mkv"])


class ReportTests(unittest.TestCase):
    def test_saved_values(self) -> None:
        report = CompressReport(original_bytes=1000, new_bytes=480)
        self.assertEqual(report.saved_bytes, 520)
        self.assertAlmostEqual(report.saved_percent, 52.0)
        self.assertIn("ลดลง 52%", report.describe())

    def test_larger_output_is_negative_saving(self) -> None:
        report = CompressReport(original_bytes=1000, new_bytes=1100)
        self.assertEqual(report.saved_bytes, -100)
        self.assertIn("ใหญ่ขึ้น", report.describe())

    def test_empty_original_does_not_divide_by_zero(self) -> None:
        self.assertEqual(CompressReport(0, 0).saved_percent, 0.0)


class TempDirCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.source = self.dir / "clip.mov"
        self.source.write_bytes(b"x" * 1000)
        self.output = self.dir / "clip_compressed.mp4"


class ValidateTests(TempDirCase):
    def make(self, **kwargs) -> CompressTask:
        return CompressTask(str(self.source), str(self.output), **kwargs)

    def test_presets_are_valid(self) -> None:
        for mode in PRESETS:
            self.make(mode=mode).validate()

    def test_unknown_mode_raises_thai_input_error(self) -> None:
        with self.assertRaises(InputError) as ctx:
            self.make(mode="ultra").validate()
        self.assertIn("โหมด", str(ctx.exception))

    def test_custom_without_kbps_raises(self) -> None:
        for kbps in (None, 0, -1):
            with self.assertRaises(InputError):
                self.make(mode="custom", target_kbps=kbps).validate()

    def test_custom_with_kbps_is_valid(self) -> None:
        self.make(mode="custom", target_kbps=4000).validate()

    def test_missing_source_raises(self) -> None:
        with self.assertRaises(InputError):
            CompressTask(str(self.dir / "nope.mp4"), str(self.output)).validate()

    def test_output_must_differ_from_source(self) -> None:
        with self.assertRaises(InputError):
            CompressTask(str(self.source), str(self.source)).validate()

    def test_summary(self) -> None:
        self.assertEqual(self.make(mode="balanced").summary(), "Balanced · −50%")
        self.assertEqual(self.make(mode="small").summary(), "Small Size · −70%")
        self.assertEqual(self.make(mode="custom", target_kbps=6000).summary(), "Custom · 6000 kbps")


class OutputPathTests(TempDirCase):
    def test_first_choice(self) -> None:
        self.assertEqual(suggest_output_path(str(self.source)), self.output)

    def test_existing_file_gets_a_number(self) -> None:
        self.output.write_bytes(b"")
        self.assertEqual(suggest_output_path(str(self.source)), self.dir / "clip_compressed_2.mp4")

    def test_queued_names_are_skipped(self) -> None:
        taken = {str(self.output), str(self.dir / "clip_compressed_2.mp4")}
        self.assertEqual(suggest_output_path(str(self.source), taken), self.dir / "clip_compressed_3.mp4")


class ProcessTests(TempDirCase):
    """process() with probe_format and run_ffmpeg mocked out."""

    def run_task(self, fake_ffmpeg, **kwargs) -> tuple[CompressTask, list[int]]:
        task = CompressTask(str(self.source), str(self.output), **kwargs)
        seen: list[int] = []
        task.set_progress_callback(lambda percent, _msg: seen.append(percent))
        info = {"duration": "10.0", "size": "1000"}
        with mock.patch("tasks.compressor.probe_format", return_value=info), \
                mock.patch("tasks.compressor.run_ffmpeg", side_effect=fake_ffmpeg):
            task.run()
        return task, seen

    def test_success_writes_output_and_report(self) -> None:
        captured: dict[str, list[str]] = {}

        def fake(args, *, duration, on_progress, is_cancelled):
            captured["args"] = list(args)
            self.assertEqual(duration, 10.0)
            Path(args[-1]).write_bytes(b"y" * 400)
            on_progress(0.5)

        task, seen = self.run_task(fake, mode="balanced")
        self.assertEqual(task.status, TaskStatus.DONE)
        self.assertEqual(self.output.read_bytes(), b"y" * 400)
        self.assertFalse(Path(captured["args"][-1]).exists())  # .part was moved, not left behind
        self.assertTrue(captured["args"][-1].endswith(".part"))
        self.assertEqual(task.result, CompressReport(original_bytes=1000, new_bytes=400))
        self.assertIn(50, seen)
        self.assertEqual(seen[-1], 100)

    def test_bitrates_come_from_preset(self) -> None:
        captured: dict[str, list[str]] = {}

        def fake(args, **_kwargs):
            captured["args"] = list(args)
            Path(args[-1]).write_bytes(b"y")

        self.run_task(fake, mode="custom", target_kbps=1000)
        args = captured["args"]
        self.assertEqual(args[args.index("-b:v") + 1], "872k")
        self.assertEqual(args[args.index("-b:a") + 1], "128k")

    def test_cancel_removes_partial_and_creates_no_output(self) -> None:
        partials: list[str] = []

        def fake(args, **_kwargs):
            partials.append(args[-1])
            Path(args[-1]).write_bytes(b"half")
            raise TaskCancelledError("ยกเลิกงานแล้ว")

        task = CompressTask(str(self.source), str(self.output))
        with mock.patch("tasks.compressor.probe_format", return_value={"duration": "10"}), \
                mock.patch("tasks.compressor.run_ffmpeg", side_effect=fake):
            with self.assertRaises(TaskCancelledError):
                task.run()
        self.assertEqual(task.status, TaskStatus.CANCELLED)
        self.assertFalse(self.output.exists())
        self.assertFalse(Path(partials[0]).exists())
        self.assertIsNone(task.result)

    def test_missing_duration_fails_with_thai_message(self) -> None:
        task = CompressTask(str(self.source), str(self.output))
        with mock.patch("tasks.compressor.probe_format", return_value={"duration": "N/A"}):
            with self.assertRaises(ToolFailedError):
                task.run()
        self.assertEqual(task.status, TaskStatus.FAILED)


if __name__ == "__main__":
    unittest.main()

