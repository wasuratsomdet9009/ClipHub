"""Tests for Feature 4 (tasks/subtitle.py). No faster-whisper, ffmpeg or network needed."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from core.base_task import TaskStatus
from core.errors import InputError, TaskCancelledError, ToolNotFoundError
from tasks.subtitle import (
    Cue,
    SubtitleTask,
    format_srt_time,
    format_vtt_time,
    render_srt,
    render_vtt,
    write_subtitles,
)

TWO_CUES = (
    Cue(0.0, 3.4, "สวัสดีครับ"),
    Cue(3.4, 7.12, "Hello world"),
)


class TimecodeTests(unittest.TestCase):
    def test_srt_edge_cases(self) -> None:
        self.assertEqual(format_srt_time(0), "00:00:00,000")
        self.assertEqual(format_srt_time(3.4), "00:00:03,400")
        self.assertEqual(format_srt_time(59.9996), "00:01:00,000")
        self.assertEqual(format_srt_time(3600.5), "01:00:00,500")

    def test_negative_clamps_to_zero(self) -> None:
        self.assertEqual(format_srt_time(-5), "00:00:00,000")
        self.assertEqual(format_vtt_time(-0.001), "00:00:00.000")

    def test_vtt_uses_dot_separator(self) -> None:
        self.assertEqual(format_vtt_time(0), "00:00:00.000")
        self.assertEqual(format_vtt_time(59.9996), "00:01:00.000")
        self.assertEqual(format_vtt_time(3725.042), "01:02:05.042")


class RenderTests(unittest.TestCase):
    def test_render_srt_two_cues(self) -> None:
        expected = (
            "1\n00:00:00,000 --> 00:00:03,400\nสวัสดีครับ\n\n"
            "2\n00:00:03,400 --> 00:00:07,120\nHello world\n\n"
        )
        self.assertEqual(render_srt(TWO_CUES), expected)

    def test_render_vtt_header_and_cues(self) -> None:
        text = render_vtt(TWO_CUES)
        self.assertTrue(text.startswith("WEBVTT\n\n"))
        self.assertIn("00:00:03.400 --> 00:00:07.120\nHello world\n\n", text)

    def test_empty_text_is_skipped_and_numbering_stays_continuous(self) -> None:
        cues = (Cue(0, 1, "  one  "), Cue(1, 2, "   "), Cue(2, 3, "two"))
        self.assertEqual(
            render_srt(cues),
            "1\n00:00:00,000 --> 00:00:01,000\none\n\n"
            "2\n00:00:02,000 --> 00:00:03,000\ntwo\n\n",
        )

    def test_blank_line_inside_text_cannot_split_a_cue(self) -> None:
        text = render_srt((Cue(0, 1, "a\n\n  b  "),))
        self.assertEqual(text, "1\n00:00:00,000 --> 00:00:01,000\na\nb\n\n")

    def test_vtt_escapes_markup_characters(self) -> None:
        text = render_vtt((Cue(0, 1, "a < b & c"),))
        self.assertIn("a &lt; b &amp; c", text)


class WriteSubtitlesTests(unittest.TestCase):
    def test_writes_srt_and_vtt_without_bom(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            srt = write_subtitles(TWO_CUES, Path(tmp) / "a.srt")
            vtt = write_subtitles(TWO_CUES, Path(tmp) / "a.vtt")
            self.assertEqual(srt.read_text(encoding="utf-8"), render_srt(TWO_CUES))
            self.assertEqual(vtt.read_text(encoding="utf-8"), render_vtt(TWO_CUES))
            self.assertFalse(srt.read_bytes().startswith(b"\xef\xbb\xbf"))
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["a.srt", "a.vtt"])

    def test_suffix_is_case_insensitive_and_returns_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = write_subtitles(TWO_CUES, str(Path(tmp) / "A.SRT"))
            self.assertIsInstance(out, Path)
            self.assertTrue(out.is_file())

    def test_rejects_other_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(InputError):
                write_subtitles(TWO_CUES, Path(tmp) / "a.txt")
            self.assertEqual(list(Path(tmp).iterdir()), [])


class ValidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.media = Path(self._tmp.name) / "talk.mp3"
        self.media.write_bytes(b"fake")
        self.out = str(self.media.with_suffix(".srt"))

    def make(self, **kwargs) -> SubtitleTask:
        return SubtitleTask(str(self.media), self.out, **kwargs)

    def test_defaults_are_valid(self) -> None:
        task = self.make()
        task.validate()
        self.assertEqual((task.language, task.model_size, task.write_file), ("th", "base", True))
        self.assertEqual(task.cues, ())

    def test_rejects_bad_language(self) -> None:
        with self.assertRaises(InputError):
            self.make(language="fr").validate()

    def test_rejects_bad_model(self) -> None:
        with self.assertRaises(InputError):
            self.make(model_size="large").validate()

    def test_rejects_bad_output_suffix(self) -> None:
        with self.assertRaises(InputError):
            SubtitleTask(str(self.media), str(self.media.with_suffix(".txt"))).validate()

    def test_rejects_missing_input(self) -> None:
        with self.assertRaises(InputError):
            SubtitleTask(str(self.media.with_name("none.mp3")), self.out).validate()

    def test_summary(self) -> None:
        self.assertEqual(self.make().summary(), "ภาษาไทย · base")
        self.assertEqual(self.make(language="en", model_size="small").summary(), "ภาษาอังกฤษ · small")


def _fake_whisper_module(segments_factory):
    model = mock.Mock()
    model.transcribe.side_effect = lambda *a, **k: (segments_factory(), SimpleNamespace())
    module = SimpleNamespace(WhisperModel=mock.Mock(return_value=model))
    return module, model


def _seg(start: float, end: float, text: str) -> SimpleNamespace:
    return SimpleNamespace(start=start, end=end, text=text)


class ProcessTests(unittest.TestCase):
    """SubtitleTask.process() with ffmpeg and faster-whisper replaced by mocks."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.media = Path(self._tmp.name) / "talk.mp3"
        self.media.write_bytes(b"fake")
        self.out = self.media.with_suffix(".srt")
        self.wav_paths: list[Path] = []
        self.progress: list[int] = []

    def run_task(self, task: SubtitleTask, module) -> Path:
        def fake_ffmpeg(args, **kwargs):
            wav = Path(args[-1])
            self.wav_paths.append(wav)
            self.assertTrue(wav.is_file())
            self.assertEqual(args[args.index("-f") + 1], "wav")
            kwargs["on_progress"](1.0)

        task.set_progress_callback(lambda percent, _msg: self.progress.append(percent))
        with mock.patch("tasks.subtitle.probe_duration", return_value=10.0), \
                mock.patch("tasks.subtitle.run_ffmpeg", side_effect=fake_ffmpeg), \
                mock.patch.dict(sys.modules, {"faster_whisper": module}):
            return task.run()

    def test_preview_mode_collects_cues_and_writes_nothing(self) -> None:
        module, model = _fake_whisper_module(lambda: iter([_seg(0, 2.5, " สวัสดี "), _seg(2.5, 5, "  "), _seg(5, 10, "ครับ")]))
        task = SubtitleTask(str(self.media), str(self.out), write_file=False)
        result = self.run_task(task, module)
        self.assertEqual(result, self.out)
        self.assertEqual(task.cues, (Cue(0.0, 2.5, "สวัสดี"), Cue(5.0, 10.0, "ครับ")))
        self.assertFalse(self.out.exists())
        module.WhisperModel.assert_called_once_with("base", device="cpu", compute_type="int8")
        model.transcribe.assert_called_once()
        self.assertEqual(model.transcribe.call_args.kwargs, {"language": "th", "vad_filter": True})
        self.assertEqual(task.status, TaskStatus.DONE)
        self.assertEqual(self.progress[-1], 100)
        self.assertEqual(self.progress, sorted(self.progress))
        self.assertFalse(self.wav_paths[0].exists())  # temp WAV cleaned up

    def test_write_mode_saves_subtitle_file(self) -> None:
        module, _ = _fake_whisper_module(lambda: iter([_seg(0, 3.4, "hello")]))
        task = SubtitleTask(str(self.media), str(self.out), language="en", write_file=True)
        self.run_task(task, module)
        self.assertEqual(self.out.read_text(encoding="utf-8"), "1\n00:00:00,000 --> 00:00:03,400\nhello\n\n")

    def test_cancel_between_segments(self) -> None:
        task = SubtitleTask(str(self.media), str(self.out))

        def segments():
            yield _seg(0, 1, "one")
            task.cancel_task()
            yield _seg(1, 2, "two")

        module, _ = _fake_whisper_module(segments)
        with self.assertRaises(TaskCancelledError):
            self.run_task(task, module)
        self.assertEqual(task.status, TaskStatus.CANCELLED)
        self.assertFalse(self.out.exists())
        self.assertFalse(self.wav_paths[0].exists())

    def test_missing_faster_whisper_raises_thai_tool_error(self) -> None:
        task = SubtitleTask(str(self.media), str(self.out))
        with mock.patch.dict(sys.modules, {"faster_whisper": None}):
            with self.assertRaises(ToolNotFoundError) as ctx:
                task.run()
        self.assertIn("faster-whisper", str(ctx.exception))
        self.assertEqual(task.status, TaskStatus.FAILED)


if __name__ == "__main__":
    unittest.main()

