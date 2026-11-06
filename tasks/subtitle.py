"""Feature 4: speech-to-text and subtitle engine (owner: member 4)."""
from __future__ import annotations

import math
import os
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from core.base_task import BaseMediaTask
from core.errors import ClipHubError, InputError, ToolFailedError, ToolNotFoundError
from core.ffmpeg import probe_duration, run_ffmpeg

LANGUAGE_NAMES = {"th": "ภาษาไทย", "en": "ภาษาอังกฤษ"}
MODEL_SIZES = ("tiny", "base", "small")
SUBTITLE_SUFFIXES = (".srt", ".vtt")

EXTRACT_END = 30      # progress % when the audio track has been extracted
TRANSCRIBE_END = 95   # progress % when the last segment has been transcribed


def _split_time(seconds: float) -> tuple[int, int, int, int]:
    """Round to whole milliseconds first so 59.9996 carries into the next minute."""
    if math.isfinite(seconds) and seconds > 0:
        total_ms = math.floor(seconds * 1000 + 0.5)
    else:
        total_ms = 0
    hours, rest = divmod(total_ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, millis = divmod(rest, 1000)
    return hours, minutes, secs, millis


def format_srt_time(seconds: float) -> str:
    """HH:MM:SS,mmm"""
    hours, minutes, secs, millis = _split_time(seconds)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_vtt_time(seconds: float) -> str:
    """HH:MM:SS.mmm"""
    hours, minutes, secs, millis = _split_time(seconds)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


@dataclass(frozen=True)
class Cue:
    start: float  # seconds
    end: float    # seconds
    text: str


def _clean_text(text: str) -> str:
    """Strip every line and drop blank ones (a blank line would end the cue early)."""
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _usable(cues: Iterable[Cue]) -> list[Cue]:
    return [Cue(c.start, c.end, text) for c in cues if (text := _clean_text(c.text))]


def _escape_vtt(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_srt(cues: Iterable[Cue]) -> str:
    return "".join(
        f"{index}\n{format_srt_time(cue.start)} --> {format_srt_time(cue.end)}\n{cue.text}\n\n"
        for index, cue in enumerate(_usable(cues), start=1)
    )


def render_vtt(cues: Iterable[Cue]) -> str:
    body = "".join(
        f"{format_vtt_time(cue.start)} --> {format_vtt_time(cue.end)}\n{_escape_vtt(cue.text)}\n\n"
        for cue in _usable(cues)
    )
    return "WEBVTT\n\n" + body


def write_subtitles(cues: Iterable[Cue], path: str | Path) -> Path:
    """Write .srt or .vtt (chosen by suffix) as UTF-8 without BOM, via a .part file."""
    target = Path(path)
    suffix = target.suffix.lower()
    if suffix == ".srt":
        content = render_srt(cues)
    elif suffix == ".vtt":
        content = render_vtt(cues)
    else:
        raise InputError("รองรับเฉพาะไฟล์ซับไตเติลนามสกุล .srt และ .vtt")
    partial = target.with_name(target.name + ".part")
    try:
        partial.write_text(content, encoding="utf-8", newline="\n")
        partial.replace(target)
    except OSError as exc:
        partial.unlink(missing_ok=True)
        raise ClipHubError(f"บันทึกไฟล์ซับไตเติลไม่สำเร็จ: {exc.strerror or exc}") from exc
    return target


def _import_whisper_model():
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise ToolNotFoundError(
            "ไม่พบไลบรารี faster-whisper กรุณาติดตั้งด้วยคำสั่ง pip install faster-whisper"
        ) from exc
    return WhisperModel


class SubtitleTask(BaseMediaTask):
    kind: ClassVar[str] = "subtitle"
    title: ClassVar[str] = "ถอดเสียงซับไตเติล"

    def __init__(
        self,
        input_path: str,
        output_path: str,
        language: str = "th",
        model_size: str = "base",
        write_file: bool = True,
    ) -> None:
        super().__init__(input_path, output_path)
        self.language = language
        self.model_size = model_size
        self.write_file = write_file
        self.cues: tuple[Cue, ...] = ()

    def summary(self) -> str:
        return f"{LANGUAGE_NAMES.get(self.language, self.language)} · {self.model_size}"

    def validate(self) -> None:
        super().validate()
        if self.language not in LANGUAGE_NAMES:
            raise InputError("ภาษาที่เลือกไม่รองรับ เลือกได้เฉพาะภาษาไทย (th) หรือภาษาอังกฤษ (en)")
        if self.model_size not in MODEL_SIZES:
            raise InputError("ขนาดโมเดลไม่ถูกต้อง เลือกได้เฉพาะ tiny, base หรือ small")
        if Path(self.output_path).suffix.lower() not in SUBTITLE_SUFFIXES:
            raise InputError("ไฟล์ปลายทางต้องมีนามสกุล .srt หรือ .vtt")

    def process(self) -> Path:
        whisper_model = _import_whisper_model()  # fail before spending time on ffmpeg
        duration = probe_duration(self.input_path)

        wav = self._temp_wav()
        self.report_progress(0, "กำลังแยกเสียงจากไฟล์")
        run_ffmpeg(
            [
                "-i", self.input_path, "-vn", "-ac", "1", "-ar", "16000",
                "-c:a", "pcm_s16le", "-f", "wav", str(wav),
            ],
            duration=duration,
            on_progress=lambda fraction: self.report_progress(
                fraction * EXTRACT_END, "กำลังแยกเสียงจากไฟล์"
            ),
            is_cancelled=self._cancel_event.is_set,
        )
        self.check_cancelled()

        self.report_progress(EXTRACT_END, "กำลังโหลดโมเดล AI (ครั้งแรกต้องดาวน์โหลดจากอินเทอร์เน็ต)")
        try:
            model = whisper_model(self.model_size, device="cpu", compute_type="int8")
        except Exception as exc:
            raise ToolFailedError(
                f"โหลดโมเดล AI ({self.model_size}) ไม่สำเร็จ "
                f"หากใช้งานครั้งแรกกรุณาตรวจสอบการเชื่อมต่ออินเทอร์เน็ต: {exc}"
            ) from exc
        self.check_cancelled()

        segments, _info = model.transcribe(str(wav), language=self.language, vad_filter=True)
        cues: list[Cue] = []
        for segment in segments:
            self.check_cancelled()
            text = segment.text.strip()
            if text:
                cues.append(Cue(float(segment.start), float(segment.end), text))
            done = min(float(segment.end) / duration, 1.0)
            self.report_progress(
                EXTRACT_END + (TRANSCRIBE_END - EXTRACT_END) * done,
                f"กำลังถอดเสียง · {len(cues)} ประโยค",
            )
        self.check_cancelled()

        self.cues = tuple(cues)
        if self.write_file:
            self.report_progress(TRANSCRIBE_END, "กำลังบันทึกไฟล์ซับไตเติล")
            write_subtitles(self.cues, self.output_path)
        return Path(self.output_path)

    def _temp_wav(self) -> Path:
        fd, name = tempfile.mkstemp(prefix="cliphub_", suffix=".wav")
        os.close(fd)
        return self.register_temp(Path(name))

