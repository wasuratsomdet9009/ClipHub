"""Feature 3: media compressor, H.264/AAC through FFmpeg (owner: member 3)."""
from __future__ import annotations

import os
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from core.base_task import BaseMediaTask
from core.errors import InputError, ToolFailedError
from core.ffmpeg import probe_format, run_ffmpeg

# --- bitrate math (SRS 3.3.1, 3.3.2.1) ---------------------------------------

PRESETS: dict[str, float] = {"high": 0.20, "balanced": 0.50, "small": 0.70}  # share removed
PRESET_LABELS: dict[str, str] = {"high": "High Quality", "balanced": "Balanced", "small": "Small Size"}
CUSTOM_MODE = "custom"
DEFAULT_AUDIO_KBPS = 128
MIN_VIDEO_KBPS = 200


def original_kbps(size_bytes: int, duration_s: float) -> float:
    """Average total bitrate (video + audio) of the source file."""
    if duration_s <= 0:
        raise ValueError("duration_s must be > 0")
    return size_bytes * 8 / 1000 / duration_s


def target_total_kbps(
    size_bytes: int, duration_s: float, mode: str, target_kbps: int | None = None
) -> float:
    """Total (video + audio) kbps the output should have."""
    if mode == CUSTOM_MODE:
        if target_kbps is None or target_kbps <= 0:
            raise ValueError("custom mode needs target_kbps > 0")
        return float(target_kbps)
    if mode not in PRESETS:
        raise ValueError(f"unknown mode: {mode}")
    return original_kbps(size_bytes, duration_s) * (1 - PRESETS[mode])


def split_bitrate(total_kbps: float, audio_kbps: int = DEFAULT_AUDIO_KBPS) -> tuple[int, int]:
    """Return (video_kbps, audio_kbps). Video never drops below MIN_VIDEO_KBPS."""
    return max(MIN_VIDEO_KBPS, round(total_kbps - audio_kbps)), audio_kbps


def estimate_output_bytes(
    size_bytes: int, duration_s: float, mode: str, target_kbps: int | None = None
) -> int:
    """Expected output size before encoding, using the same split the encoder will get."""
    total = target_total_kbps(size_bytes, duration_s, mode, target_kbps)
    video_kbps, audio_kbps = split_bitrate(total)
    return int((video_kbps + audio_kbps) * 1000 / 8 * duration_s)


def format_size(num_bytes: float) -> str:
    """Decimal units to match the mockup: 595 MB, 1.24 GB."""
    if num_bytes >= 1e9:
        return f"{num_bytes / 1e9:.2f} GB"
    if num_bytes >= 1e8:
        return f"{num_bytes / 1e6:.0f} MB"
    if num_bytes >= 1e6:
        return f"{num_bytes / 1e6:.1f} MB"
    return f"{num_bytes / 1e3:.0f} KB"


# --- ffmpeg command (SRS 3.3.1.3) ---------------------------------------------


def build_compress_args(
    input_path: str, partial_path: str, video_kbps: int, audio_kbps: int
) -> list[str]:
    """Arguments for core.ffmpeg.run_ffmpeg. The partial path must stay the last item."""
    return [
        "-i", input_path,
        "-map", "0:v:0", "-map", "0:a:0?",  # first video, optional first audio; skips subtitles
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",  # yuv420p needs even dimensions
        "-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-b:v", f"{video_kbps}k", "-maxrate", f"{video_kbps}k", "-bufsize", f"{video_kbps * 2}k",
        "-c:a", "aac", "-b:a", f"{audio_kbps}k",
        "-movflags", "+faststart",
        "-f", "mp4",
        partial_path,
    ]


def suggest_output_path(input_path: str, taken: Collection[str] = ()) -> Path:
    """Same folder, '<stem>_compressed.mp4', numbered until it is unused on disk and in `taken`."""
    source = Path(input_path)
    reserved = {os.path.normcase(item) for item in taken}
    number = 1
    while True:
        suffix = "" if number == 1 else f"_{number}"
        candidate = source.with_name(f"{source.stem}_compressed{suffix}.mp4")
        if not candidate.exists() and os.path.normcase(str(candidate)) not in reserved:
            return candidate
        number += 1


# --- task (SRS 3.3.2.2, 3.3.2.3) ----------------------------------------------


@dataclass(frozen=True)
class CompressReport:
    original_bytes: int
    new_bytes: int

    @property
    def saved_bytes(self) -> int:
        return self.original_bytes - self.new_bytes

    @property
    def saved_percent(self) -> float:
        if self.original_bytes <= 0:
            return 0.0
        return self.saved_bytes / self.original_bytes * 100

    def describe(self) -> str:
        if self.saved_bytes >= 0:
            change = f"ลดลง {self.saved_percent:.0f}%"
        else:
            change = f"ใหญ่ขึ้น {-self.saved_percent:.0f}%"
        return f"{format_size(self.original_bytes)} → {format_size(self.new_bytes)} ({change})"


class CompressTask(BaseMediaTask):
    kind: ClassVar[str] = "compress"
    title: ClassVar[str] = "บีบอัดไฟล์"

    def __init__(
        self,
        input_path: str,
        output_path: str,
        mode: str = "balanced",
        target_kbps: int | None = None,
    ) -> None:
        super().__init__(input_path, output_path)
        self.mode = mode
        self.target_kbps = target_kbps
        self.result: CompressReport | None = None  # set after a successful run

    def summary(self) -> str:
        if self.mode == CUSTOM_MODE:
            return f"Custom · {self.target_kbps} kbps"
        label = PRESET_LABELS.get(self.mode, self.mode)
        if self.mode in PRESETS:
            return f"{label} · −{round(PRESETS[self.mode] * 100)}%"
        return label

    def validate(self) -> None:
        super().validate()
        if self.mode != CUSTOM_MODE and self.mode not in PRESETS:
            raise InputError(f"ไม่รู้จักโหมดการบีบอัด: {self.mode}")
        if self.mode == CUSTOM_MODE and (self.target_kbps is None or self.target_kbps <= 0):
            raise InputError("กรุณาระบุ Target Bitrate (kbps) เป็นตัวเลขมากกว่า 0")
        if Path(self.input_path).resolve() == Path(self.output_path).resolve():
            raise InputError("ไฟล์ปลายทางต้องไม่ใช่ไฟล์เดียวกับไฟล์ต้นฉบับ")

    def _read_source(self) -> tuple[int, float]:
        info = probe_format(self.input_path)
        try:
            duration = float(info.get("duration") or 0)
        except ValueError:
            duration = 0.0
        if duration <= 0:
            raise ToolFailedError("ไม่พบความยาวของไฟล์")
        try:
            size = int(info["size"])
        except (KeyError, TypeError, ValueError):
            size = os.path.getsize(self.input_path)
        return size, duration

    def process(self) -> Path:
        size, duration = self._read_source()
        total = target_total_kbps(size, duration, self.mode, self.target_kbps)
        video_kbps, audio_kbps = split_bitrate(total)

        partial = self.partial_output()
        run_ffmpeg(
            build_compress_args(self.input_path, str(partial), video_kbps, audio_kbps),
            duration=duration,
            on_progress=lambda fraction: self.report_progress(fraction * 100, "กำลังบีบอัด"),
            is_cancelled=self._cancel_event.is_set,
        )
        self.check_cancelled()

        final = Path(self.output_path)
        partial.replace(final)
        self.result = CompressReport(original_bytes=size, new_bytes=final.stat().st_size)
        return final

