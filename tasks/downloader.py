"""Feature 1: video downloader (owner: member 1)."""
from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import parse_qs, urlparse

from core.base_task import BaseMediaTask
from core.errors import InputError, TaskCancelledError, ToolFailedError
from core.ffmpeg import find_tool

QUALITIES = ("360p", "720p", "1080p", "1440p", "2160p", "best")
DEFAULT_QUALITY = "1080p"
INVALID_URL_MESSAGE = "ลิงก์ YouTube ไม่ถูกต้อง"

_VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com"}
_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*://")
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_MB = 1024 * 1024


def normalize_youtube_url(url: str) -> str:
    url = url.strip()
    return url if _SCHEME.match(url) else f"https://{url}"


def is_valid_youtube_url(url: str) -> bool:
    """Accepts watch?v=, youtu.be/ and shorts/ links with a 11-character id, with or without scheme."""
    if not isinstance(url, str):
        return False
    text = url.strip()
    if not text or any(ch.isspace() for ch in text):
        return False
    try:
        parsed = urlparse(normalize_youtube_url(text))
        host = (parsed.hostname or "").lower()
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    if host == "youtu.be":
        return bool(_VIDEO_ID.fullmatch(parsed.path.removeprefix("/").removesuffix("/")))
    if host not in _YOUTUBE_HOSTS:
        return False
    if parsed.path.rstrip("/") == "/watch":
        values = parse_qs(parsed.query).get("v", [""])
        return bool(_VIDEO_ID.fullmatch(values[0]))
    if parsed.path.startswith("/shorts/"):
        return bool(_VIDEO_ID.fullmatch(parsed.path.removeprefix("/shorts/").removesuffix("/")))
    return False


def build_format_selector(quality: str, audio_only: bool) -> str:
    if audio_only:
        return "bestaudio/best"
    key = (quality or "").strip().lower()
    if key == "best":
        return "bestvideo+bestaudio/best"
    if key in QUALITIES:
        height = key.removesuffix("p")
        return f"bestvideo[height<={height}]+bestaudio/best[height<={height}]"
    raise InputError(f"ไม่รองรับความละเอียด: {quality}")


def parse_metadata(info: dict[str, Any]) -> dict[str, Any]:
    """Pick the fields the UI shows out of yt-dlp's info dict."""
    heights = {
        int(fmt["height"])
        for fmt in info.get("formats") or []
        if fmt.get("height") and fmt.get("vcodec") != "none"
    }
    if not heights and info.get("height"):
        heights.add(int(info["height"]))
    thumbnail = info.get("thumbnail") or ""
    if not thumbnail:
        thumbs = [t.get("url") for t in info.get("thumbnails") or [] if t.get("url")]
        thumbnail = thumbs[-1] if thumbs else ""
    return {
        "title": info.get("title") or "",
        "duration": int(info.get("duration") or 0),
        "thumbnail": thumbnail,
        "uploader": info.get("uploader") or info.get("channel") or "",
        "heights": sorted(heights),
    }


def format_duration(seconds: int) -> str:
    """12:34 or 1:02:03."""
    seconds = max(int(seconds), 0)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def fetch_metadata(url: str) -> dict[str, Any]:
    """Blocking network call: run it off the GUI thread."""
    if not is_valid_youtube_url(url):
        raise InputError(INVALID_URL_MESSAGE)
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError

    options = {"quiet": True, "no_warnings": True, "noplaylist": True, "skip_download": True, "socket_timeout": 20}
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(normalize_youtube_url(url), download=False)
    except DownloadError as exc:
        raise ToolFailedError(f"ดึงข้อมูลวิดีโอไม่สำเร็จ: {_clean_error(exc)}") from exc
    if not info:
        raise ToolFailedError("ดึงข้อมูลวิดีโอไม่สำเร็จ: ไม่พบข้อมูลวิดีโอ")
    return parse_metadata(info)


def _clean_error(exc: BaseException) -> str:
    text = _ANSI.sub("", str(exc)).strip().removeprefix("ERROR:").strip()
    return text[:300] or "ไม่ทราบสาเหตุ"


def _final_path(info: Any) -> Path | None:
    """Where yt-dlp left the finished file (after merge / audio extraction)."""
    if not isinstance(info, dict):
        return None
    for entry in info.get("requested_downloads") or []:
        found = entry.get("filepath") or entry.get("_filename")
        if found:
            return Path(found)
    found = info.get("filepath") or info.get("_filename")
    return Path(found) if found else None


class DownloaderTask(BaseMediaTask):
    kind: ClassVar[str] = "download"
    title: ClassVar[str] = "ดาวน์โหลดวิดีโอ"
    fetch_metadata = staticmethod(fetch_metadata)

    def __init__(
        self,
        url: str,
        output_dir: str,
        quality: str = "1080p",
        audio_only: bool = False,
        video_title: str = "",
    ) -> None:
        super().__init__(url, output_dir)
        self.quality = quality
        self.audio_only = audio_only
        self.display_name = video_title.strip() or url.strip()  # shown on the queue card
        self.downloaded_file: Path | None = None
        self._temp_dir: Path | None = None
        self._streams: dict[str, tuple[float, float]] = {}
        self._last_percent = 0

    def summary(self) -> str:
        if self.audio_only:
            return "เสียง · MP3"
        label = "สูงสุด" if self.quality.lower() == "best" else self.quality
        return f"{label} · MP4"

    def validate(self) -> None:
        if not is_valid_youtube_url(self.input_path):
            raise InputError(INVALID_URL_MESSAGE)
        if not str(self.output_path).strip():
            raise InputError("ยังไม่ได้เลือกโฟลเดอร์ปลายทาง")
        build_format_selector(self.quality, self.audio_only)  # rejects an unknown quality

    def process(self) -> Path:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import DownloadError

        ffmpeg_dir = str(Path(find_tool("ffmpeg")).parent)
        out_dir = Path(self.output_path).expanduser()
        self._streams = {}
        self._last_percent = 0
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            self._temp_dir = Path(tempfile.mkdtemp(prefix=".cliphub-", dir=out_dir))
        except OSError as exc:
            raise ToolFailedError(f"สร้างโฟลเดอร์ปลายทางไม่ได้: {exc}") from exc

        options: dict[str, Any] = {
            "format": build_format_selector(self.quality, self.audio_only),
            # Relative template: "paths" puts the result in out_dir and keeps partial files in the temp dir.
            # Video names carry the height, so a second download at another quality is not skipped as "already downloaded".
            "outtmpl": (
                "%(title).180B [%(id)s].%(ext)s" if self.audio_only
                else "%(title).180B [%(id)s] %(height)sp.%(ext)s"
            ),
            "paths": {"home": str(out_dir), "temp": str(self._temp_dir)},
            "ffmpeg_location": ffmpeg_dir,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "windowsfilenames": True,
            "retries": 5,
            "fragment_retries": 5,
            "socket_timeout": 30,
            "progress_hooks": [self._on_download_progress],
            "postprocessor_hooks": [self._on_postprocess],
        }
        if self.audio_only:
            options["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
            ]
        else:
            options["format_sort"] = ["res", "ext:mp4:m4a"]  # prefer MP4-friendly streams at equal resolution
            options["merge_output_format"] = "mp4"

        self.report_progress(0, "กำลังเตรียมดาวน์โหลด…")
        try:
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(normalize_youtube_url(self.input_path), download=True)
        except TaskCancelledError:
            raise
        except DownloadError as exc:
            if self._cancel_event.is_set():
                raise TaskCancelledError("ยกเลิกงานแล้ว") from exc
            raise ToolFailedError(f"ดาวน์โหลดไม่สำเร็จ: {_clean_error(exc)}") from exc
        except OSError as exc:
            raise ToolFailedError(f"ดาวน์โหลดไม่สำเร็จ: {exc}") from exc

        self.check_cancelled()
        final = _final_path(info)
        if final is None or not final.is_file():
            raise ToolFailedError("ดาวน์โหลดไม่สำเร็จ: ไม่พบไฟล์ผลลัพธ์")
        self.downloaded_file = final
        return final

    def cleanup(self) -> None:
        super().cleanup()
        if self._temp_dir is not None:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None

    def _on_download_progress(self, data: dict[str, Any]) -> None:
        self.check_cancelled()
        status = data.get("status")
        if status not in ("downloading", "finished"):
            return
        key = str(data.get("filename") or data.get("tmpfilename") or "")
        done = float(data.get("downloaded_bytes") or 0)
        total = float(data.get("total_bytes") or data.get("total_bytes_estimate") or 0)
        if status == "finished":
            total = done = max(done, total)
        self._streams[key] = (done, total)
        # Video and audio arrive as separate streams, so sum them to keep the bar moving forward.
        done_sum = sum(d for d, _ in self._streams.values())
        total_sum = sum(t for _, t in self._streams.values())
        if total_sum > 0:
            self._last_percent = max(self._last_percent, min(int(done_sum / total_sum * 100), 99))
            text = f"กำลังดาวน์โหลด {done_sum / _MB:.1f} / {total_sum / _MB:.1f} MB"
        else:
            text = f"กำลังดาวน์โหลด {done_sum / _MB:.1f} MB"
        speed = data.get("speed")
        if speed:
            text += f" · {speed / _MB:.1f} MB/s"
        self.report_progress(self._last_percent, text)

    def _on_postprocess(self, data: dict[str, Any]) -> None:
        self.check_cancelled()
        name = str(data.get("postprocessor") or "")
        if data.get("status") != "started":
            return
        if "ExtractAudio" in name:
            self.report_progress(99, "กำลังแปลงเป็น MP3…")
        elif "Merger" in name:
            self.report_progress(99, "กำลังรวมวิดีโอและเสียง…")
