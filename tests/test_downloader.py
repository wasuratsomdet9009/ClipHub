"""Tests for Feature 1: URL validation, format selector, metadata parsing and the yt-dlp task (no network)."""
from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from core.base_task import TaskStatus
from core.errors import InputError, TaskCancelledError, ToolFailedError
from tasks.downloader import (
    QUALITIES,
    DownloaderTask,
    build_format_selector,
    fetch_metadata,
    format_duration,
    is_valid_youtube_url,
    parse_metadata,
)

VIDEO_ID = "dQw4w9WgXcQ"
URL = f"https://www.youtube.com/watch?v={VIDEO_ID}"


class FakeDownloadError(Exception):
    """Stands in for yt_dlp.utils.DownloadError."""


def fake_yt_dlp(ydl_class: type):
    """Patch sys.modules so the lazy `from yt_dlp import YoutubeDL` gets a fake."""
    package = types.ModuleType("yt_dlp")
    utils = types.ModuleType("yt_dlp.utils")
    package.YoutubeDL = ydl_class
    package.utils = utils
    utils.DownloadError = FakeDownloadError
    return patch.dict(sys.modules, {"yt_dlp": package, "yt_dlp.utils": utils})


class FakeYDL:
    """Records its options; extract_info runs the scripted behaviour set on the class."""

    instances: list["FakeYDL"] = []
    behaviour = staticmethod(lambda ydl, url, download: {})

    def __init__(self, options: dict) -> None:
        self.options = options
        FakeYDL.instances.append(self)

    def __enter__(self) -> "FakeYDL":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def extract_info(self, url: str, download: bool = True) -> dict:
        self.url = url
        return type(self).behaviour(self, url, download)


class UrlValidationTests(unittest.TestCase):
    def test_valid_urls(self) -> None:
        valid = [
            URL,
            f"https://youtube.com/watch?v={VIDEO_ID}",
            f"http://m.youtube.com/watch?v={VIDEO_ID}&t=42s",
            f"youtube.com/watch?v={VIDEO_ID}",
            f"www.youtube.com/watch?v={VIDEO_ID}",
            f"https://www.youtube.com/watch?list=PL123&v={VIDEO_ID}",
            f"https://youtu.be/{VIDEO_ID}",
            f"youtu.be/{VIDEO_ID}?si=abc",
            f"https://www.youtube.com/shorts/{VIDEO_ID}",
            f"m.youtube.com/shorts/{VIDEO_ID}/",
            f"  {URL}  ",
            "https://youtu.be/a_b-c1234AZ",
        ]
        for url in valid:
            with self.subTest(url=url):
                self.assertTrue(is_valid_youtube_url(url))

    def test_invalid_urls(self) -> None:
        invalid = [
            "",
            "   ",
            "สวัสดี",
            "https://www.youtube.com/",
            "https://www.youtube.com/watch",
            "https://www.youtube.com/watch?v=short",
            f"https://www.youtube.com/watch?v={VIDEO_ID}x",
            "https://www.youtube.com/watch?v=abc!@#$%^&*(",
            f"https://vimeo.com/watch?v={VIDEO_ID}",
            f"https://notyoutube.com/watch?v={VIDEO_ID}",
            f"https://youtube.com.evil.com/watch?v={VIDEO_ID}",
            f"https://youtube.com@evil.com/watch?v={VIDEO_ID}",
            f"ftp://youtube.com/watch?v={VIDEO_ID}",
            f"https://youtu.be/{VIDEO_ID}/extra",
            f"https://www.youtube.com/shorts/{VIDEO_ID[:5]}",
            f"https://www.youtube.com/playlist?list={VIDEO_ID}",
            f"{URL} {URL}",
        ]
        for url in invalid:
            with self.subTest(url=url):
                self.assertFalse(is_valid_youtube_url(url))

    def test_non_string_is_invalid(self) -> None:
        self.assertFalse(is_valid_youtube_url(None))  # type: ignore[arg-type]


class FormatSelectorTests(unittest.TestCase):
    def test_every_video_quality(self) -> None:
        for quality in QUALITIES:
            if quality == "best":
                continue
            height = quality[:-1]
            with self.subTest(quality=quality):
                self.assertEqual(
                    build_format_selector(quality, False),
                    f"bestvideo[height<={height}]+bestaudio/best[height<={height}]",
                )

    def test_best(self) -> None:
        self.assertEqual(build_format_selector("best", False), "bestvideo+bestaudio/best")

    def test_audio_only_ignores_quality(self) -> None:
        for quality in QUALITIES:
            with self.subTest(quality=quality):
                self.assertEqual(build_format_selector(quality, True), "bestaudio/best")

    def test_unknown_quality_is_input_error(self) -> None:
        with self.assertRaises(InputError):
            build_format_selector("999p", False)


class MetadataTests(unittest.TestCase):
    INFO = {
        "title": "10 เทคนิคตัดต่อวิดีโอ",
        "duration": 754.0,
        "thumbnail": "https://i.ytimg.com/vi/x/maxresdefault.jpg",
        "uploader": "Creative Studio TH",
        "formats": [
            {"format_id": "140", "vcodec": "none", "acodec": "mp4a", "height": None},
            {"format_id": "18", "vcodec": "avc1", "height": 360},
            {"format_id": "22", "vcodec": "avc1", "height": 720},
            {"format_id": "137", "vcodec": "avc1", "height": 1080},
            {"format_id": "248", "vcodec": "vp9", "height": 1080},
            {"format_id": "313", "vcodec": "vp9", "height": 2160},
            {"format_id": "sb0", "vcodec": "none", "height": 90},
        ],
    }

    def test_parse_full_info(self) -> None:
        meta = parse_metadata(self.INFO)
        self.assertEqual(meta["title"], "10 เทคนิคตัดต่อวิดีโอ")
        self.assertEqual(meta["duration"], 754)
        self.assertIsInstance(meta["duration"], int)
        self.assertEqual(meta["thumbnail"], "https://i.ytimg.com/vi/x/maxresdefault.jpg")
        self.assertEqual(meta["uploader"], "Creative Studio TH")
        self.assertEqual(meta["heights"], [360, 720, 1080, 2160])

    def test_parse_sparse_info(self) -> None:
        meta = parse_metadata({"channel": "Chan", "thumbnails": [{"url": "a"}, {"url": "b"}], "height": 480})
        self.assertEqual(meta, {"title": "", "duration": 0, "thumbnail": "b", "uploader": "Chan", "heights": [480]})

    def test_parse_empty_info(self) -> None:
        meta = parse_metadata({})
        self.assertEqual((meta["title"], meta["duration"], meta["heights"]), ("", 0, []))

    def test_format_duration(self) -> None:
        self.assertEqual(format_duration(754), "12:34")
        self.assertEqual(format_duration(5), "00:05")
        self.assertEqual(format_duration(3723), "1:02:03")
        self.assertEqual(format_duration(-4), "00:00")

    def test_fetch_metadata_parses_yt_dlp_info(self) -> None:
        FakeYDL.instances = []
        FakeYDL.behaviour = staticmethod(lambda ydl, url, download: MetadataTests.INFO)
        with fake_yt_dlp(FakeYDL):
            meta = fetch_metadata(f"youtube.com/watch?v={VIDEO_ID}")
        ydl = FakeYDL.instances[0]
        self.assertEqual(meta["heights"], [360, 720, 1080, 2160])
        self.assertEqual(ydl.url, f"https://youtube.com/watch?v={VIDEO_ID}")
        self.assertTrue(ydl.options["noplaylist"])

    def test_fetch_metadata_maps_download_error(self) -> None:
        def boom(ydl, url, download):
            raise FakeDownloadError("\x1b[0;31mERROR:\x1b[0m Video unavailable")

        FakeYDL.behaviour = staticmethod(boom)
        with fake_yt_dlp(FakeYDL), self.assertRaises(ToolFailedError) as ctx:
            fetch_metadata(URL)
        self.assertEqual(str(ctx.exception), "ดึงข้อมูลวิดีโอไม่สำเร็จ: Video unavailable")

    def test_fetch_metadata_rejects_bad_url_before_touching_yt_dlp(self) -> None:
        with self.assertRaises(InputError):
            fetch_metadata("https://example.com/video")


class DownloaderTaskTests(unittest.TestCase):
    def test_validate_rejects_invalid_url(self) -> None:
        task = DownloaderTask("https://example.com/video", "/tmp/out")
        with self.assertRaises(InputError) as ctx:
            task.validate()
        self.assertEqual(str(ctx.exception), "ลิงก์ YouTube ไม่ถูกต้อง")

    def test_validate_rejects_empty_folder_and_bad_quality(self) -> None:
        with self.assertRaises(InputError):
            DownloaderTask(URL, "  ").validate()
        with self.assertRaises(InputError):
            DownloaderTask(URL, "/tmp/out", quality="999p").validate()

    def test_validate_accepts_good_input_without_local_file(self) -> None:
        DownloaderTask(URL, "/tmp/out", quality="720p").validate()
        DownloaderTask(f"youtu.be/{VIDEO_ID}", "/tmp/out", audio_only=True).validate()

    def test_run_reports_invalid_url_as_failed(self) -> None:
        task = DownloaderTask("nope", "/tmp/out")
        with self.assertRaises(InputError):
            task.run()
        self.assertIs(task.status, TaskStatus.FAILED)

    def test_summary(self) -> None:
        self.assertEqual(DownloaderTask(URL, "/o").summary(), "1080p · MP4")
        self.assertEqual(DownloaderTask(URL, "/o", quality="360p").summary(), "360p · MP4")
        self.assertEqual(DownloaderTask(URL, "/o", quality="best").summary(), "สูงสุด · MP4")
        self.assertEqual(DownloaderTask(URL, "/o", audio_only=True).summary(), "เสียง · MP3")

    def test_class_contract(self) -> None:
        task = DownloaderTask(URL, "/o")
        self.assertEqual((task.kind, task.title, task.quality, task.audio_only), ("download", "ดาวน์โหลดวิดีโอ", "1080p", False))
        self.assertEqual(task.display_name, URL)
        self.assertEqual(DownloaderTask(URL, "/o", video_title=" ชื่อคลิป ").display_name, "ชื่อคลิป")


class DownloaderProcessTests(unittest.TestCase):
    """process() against a fake yt-dlp and a fake ffmpeg location: no network, no binaries."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out_dir = Path(self.tmp.name) / "ClipHUB Downloads"  # does not exist yet: the task must create it
        FakeYDL.instances = []
        patcher = patch("tasks.downloader.find_tool", return_value="/opt/fake/bin/ffmpeg")
        patcher.start()
        self.addCleanup(patcher.stop)

    def _download_script(self, ext: str = "mp4", hooks: list[dict] | None = None):
        def script(ydl: FakeYDL, url: str, download: bool) -> dict:
            for data in hooks or []:
                for hook in ydl.options["progress_hooks"]:
                    hook(data)
            home = Path(ydl.options["paths"]["home"])
            temp = Path(ydl.options["paths"]["temp"])
            (temp / "leftover.part").write_bytes(b"x")
            final = home / f"clip [{VIDEO_ID}].{ext}"
            final.write_bytes(b"video")
            return {"requested_downloads": [{"filepath": str(final)}]}

        return staticmethod(script)

    def test_video_download_options_and_result(self) -> None:
        hooks = [
            {"status": "downloading", "filename": "v.f137.mp4", "downloaded_bytes": 5_000_000, "total_bytes": 10_000_000, "speed": 2_097_152},
            {"status": "finished", "filename": "v.f137.mp4", "downloaded_bytes": 10_000_000, "total_bytes": 10_000_000},
            {"status": "downloading", "filename": "v.f140.m4a", "downloaded_bytes": 100_000, "total_bytes_estimate": 1_000_000},
            {"status": "finished", "filename": "v.f140.m4a", "downloaded_bytes": 1_000_000},
        ]
        FakeYDL.behaviour = self._download_script(hooks=hooks)
        task = DownloaderTask(URL, str(self.out_dir), quality="720p")
        calls: list[tuple[int, str]] = []
        task.set_progress_callback(lambda percent, message: calls.append((percent, message)))
        with fake_yt_dlp(FakeYDL):
            result = task.run()

        options = FakeYDL.instances[0].options
        self.assertEqual(options["format"], "bestvideo[height<=720]+bestaudio/best[height<=720]")
        self.assertEqual(options["ffmpeg_location"], "/opt/fake/bin")
        self.assertEqual(options["paths"]["home"], str(self.out_dir))
        self.assertTrue(options["noplaylist"])
        self.assertEqual(options["merge_output_format"], "mp4")
        self.assertNotIn("postprocessors", options)
        self.assertEqual(FakeYDL.instances[0].url, URL)

        self.assertEqual(result, self.out_dir / f"clip [{VIDEO_ID}].mp4")
        self.assertTrue(result.is_file())
        self.assertIs(task.status, TaskStatus.DONE)
        self.assertEqual(task.downloaded_file, result)
        percents = [p for p, _ in calls]
        self.assertEqual(percents, sorted(percents))  # the bar never moves backwards
        self.assertEqual(percents[-1], 100)
        self.assertTrue(any("MB/s" in message for _, message in calls))
        self.assertTrue(any(0 < p < 100 for p in percents))

    def test_temp_dir_is_removed_and_only_the_file_remains(self) -> None:
        FakeYDL.behaviour = self._download_script()
        with fake_yt_dlp(FakeYDL):
            DownloaderTask(URL, str(self.out_dir)).run()
        self.assertEqual([p.name for p in self.out_dir.iterdir()], [f"clip [{VIDEO_ID}].mp4"])

    def test_audio_only_adds_mp3_extraction(self) -> None:
        FakeYDL.behaviour = self._download_script(ext="mp3")
        task = DownloaderTask(f"youtu.be/{VIDEO_ID}", str(self.out_dir), quality="360p", audio_only=True)
        with fake_yt_dlp(FakeYDL):
            result = task.run()
        options = FakeYDL.instances[0].options
        self.assertEqual(options["format"], "bestaudio/best")
        self.assertEqual(options["postprocessors"][0]["key"], "FFmpegExtractAudio")
        self.assertEqual(options["postprocessors"][0]["preferredcodec"], "mp3")
        self.assertEqual(result.suffix, ".mp3")
        self.assertEqual(FakeYDL.instances[0].url, f"https://youtu.be/{VIDEO_ID}")

    def test_download_error_becomes_tool_failed_error(self) -> None:
        def boom(ydl, url, download):
            raise FakeDownloadError("ERROR: Private video")

        FakeYDL.behaviour = staticmethod(boom)
        task = DownloaderTask(URL, str(self.out_dir))
        with fake_yt_dlp(FakeYDL), self.assertRaises(ToolFailedError) as ctx:
            task.run()
        self.assertEqual(str(ctx.exception), "ดาวน์โหลดไม่สำเร็จ: Private video")
        self.assertIs(task.status, TaskStatus.FAILED)
        self.assertEqual(list(self.out_dir.iterdir()), [])  # temp dir cleaned even on failure

    def test_cancel_from_progress_hook(self) -> None:
        task = DownloaderTask(URL, str(self.out_dir))

        def script(ydl, url, download):
            task.cancel_task()  # what TaskWorker.cancel() does while yt-dlp is downloading
            ydl.options["progress_hooks"][0]({"status": "downloading", "filename": "a", "downloaded_bytes": 1, "total_bytes": 10})
            return {}

        FakeYDL.behaviour = staticmethod(script)
        with fake_yt_dlp(FakeYDL), self.assertRaises(TaskCancelledError):
            task.run()
        self.assertIs(task.status, TaskStatus.CANCELLED)
        self.assertEqual(list(self.out_dir.iterdir()), [])

    def test_cancel_wrapped_in_download_error_is_still_a_cancel(self) -> None:
        task = DownloaderTask(URL, str(self.out_dir))

        def script(ydl, url, download):
            task.cancel_task()
            raise FakeDownloadError("interrupted")

        FakeYDL.behaviour = staticmethod(script)
        with fake_yt_dlp(FakeYDL), self.assertRaises(TaskCancelledError):
            task.run()

    def test_missing_result_file_is_reported(self) -> None:
        FakeYDL.behaviour = staticmethod(lambda ydl, url, download: {"requested_downloads": [{"filepath": str(self.out_dir / "gone.mp4")}]})
        with fake_yt_dlp(FakeYDL), self.assertRaises(ToolFailedError):
            DownloaderTask(URL, str(self.out_dir)).run()


if __name__ == "__main__":
    unittest.main()
