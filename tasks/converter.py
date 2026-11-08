"""Feature 2: format converter and audio separator (owner: member 2)."""
from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path
from typing import ClassVar

from core.base_task import BaseMediaTask
from core.errors import InputError, ToolFailedError
from core.ffmpeg import probe_duration, run_ffmpeg

VIDEO_TARGETS = ("mp4", "mkv", "avi", "mov")
AUDIO_TARGETS = ("mp3", "wav", "aac", "flac")
SEPARATOR_FORMATS = ("mp3", "wav")  # SRS 3.2.2: separated audio is saved as MP3 or WAV

_VIDEO_MUXER = {"mp4": "mp4", "mkv": "matroska", "avi": "avi", "mov": "mov"}
# ext -> (codec options, muxer). The muxer is explicit because temp names end in .part.
_AUDIO_ENCODE = {
    "mp3": (["-c:a", "libmp3lame", "-q:a", "2"], "mp3"),
    "wav": (["-c:a", "pcm_s16le"], "wav"),
    "aac": (["-c:a", "aac", "-b:a", "192k"], "adts"),
    "flac": (["-c:a", "flac"], "flac"),
}
# libx264 + yuv420p refuse odd frame sizes; this rounds them down to even numbers
_EVEN_SIZE = "scale=trunc(iw/2)*2:trunc(ih/2)*2"


def normalize_ext(ext: str) -> str:
    return ext.strip().lower().lstrip(".")


def _unsupported(ext: str) -> InputError:
    return InputError(f"รูปแบบ .{ext} ไม่รองรับ" if ext else "รูปแบบ (ไม่มีนามสกุล) ไม่รองรับ")


def build_convert_args(input_path: str, partial_path: str, target_ext: str) -> list[str]:
    """ffmpeg input/output options for converting into one supported target format."""
    ext = normalize_ext(target_ext)
    if ext in _VIDEO_MUXER:
        args = [
            "-i", input_path,
            "-map", "0:v:0?", "-map", "0:a?",  # skip subtitle/data streams MP4 and AVI cannot hold
            "-vf", _EVEN_SIZE,
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
        ]
        if ext == "mp4":
            args += ["-movflags", "+faststart"]
        return [*args, "-f", _VIDEO_MUXER[ext], partial_path]
    if ext in _AUDIO_ENCODE:
        codec, muxer = _AUDIO_ENCODE[ext]
        return ["-i", input_path, "-vn", *codec, "-f", muxer, partial_path]
    raise _unsupported(ext)


def build_extract_args(input_path: str, partial_path: str, audio_ext: str) -> list[str]:
    """ffmpeg options that copy the first audio stream out of a video as MP3 or WAV."""
    ext = normalize_ext(audio_ext)
    if ext not in SEPARATOR_FORMATS:
        raise InputError(f"รูปแบบเสียง .{ext} ไม่รองรับในโหมดแยกเสียง (รองรับเฉพาะ MP3 / WAV)")
    codec, muxer = _AUDIO_ENCODE[ext]
    return ["-i", input_path, "-map", "0:a:0", "-vn", *codec, "-f", muxer, partial_path]


def audio_sidecar_path(output_path: str | Path, audio_ext: str = "mp3") -> Path:
    """<output stem>_audio.<mp3|wav> in the same folder as the main output."""
    out = Path(output_path)
    return out.with_name(f"{out.stem}_audio.{normalize_ext(audio_ext)}")


def describe_conversion(source_ext: str, target_ext: str, sidecar_ext: str | None = None) -> str:
    """Text such as 'MKV → MP4 · + เสียง MP3' for the queue row and the page hint."""
    text = f"{normalize_ext(source_ext).upper() or '?'} → {normalize_ext(target_ext).upper()}"
    if sidecar_ext:
        text += f" · + เสียง {normalize_ext(sidecar_ext).upper()}"
    return text


def suggest_output_path(
    input_path: str,
    target_ext: str,
    *,
    sidecar_ext: str | None = None,
    taken: Iterable[str | Path] = (),
) -> Path:
    """<stem>_converted.<ext> beside the input, then '(2)', '(3)'... until nothing collides.

    With sidecar_ext the audio sidecar name must be free too. `taken` lists paths that are
    queued but not written yet.
    """
    src = Path(input_path)
    ext = normalize_ext(target_ext)
    reserved = {os.path.normcase(str(p)) for p in taken}
    count = 1
    while True:
        tag = "_converted" if count == 1 else f"_converted ({count})"
        candidate = src.with_name(f"{src.stem}{tag}.{ext}")
        paths = [candidate]
        if sidecar_ext:
            paths.append(audio_sidecar_path(candidate, sidecar_ext))
        if not any(p.exists() or os.path.normcase(str(p)) in reserved for p in paths):
            return candidate
        count += 1


def _same_file(a: str | Path, b: str | Path) -> bool:
    try:
        if Path(a).exists() and Path(b).exists():
            return os.path.samefile(a, b)
    except OSError:
        pass
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


class ConverterTask(BaseMediaTask):
    kind: ClassVar[str] = "convert"
    title: ClassVar[str] = "แปลงไฟล์"

    def __init__(
        self,
        input_path: str,
        output_path: str,
        extract_audio: bool = False,
        audio_format: str = "mp3",
    ) -> None:
        super().__init__(input_path, output_path)
        self.extract_audio = extract_audio
        self.audio_format = normalize_ext(audio_format)

    @property
    def target_ext(self) -> str:
        return normalize_ext(Path(self.output_path).suffix)

    @property
    def audio_output_path(self) -> Path | None:
        """Where the separated audio goes (None when extract_audio is off)."""
        if not self.extract_audio:
            return None
        return audio_sidecar_path(self.output_path, self.audio_format)

    def summary(self) -> str:
        sidecar = self.audio_format if self.extract_audio else None
        return describe_conversion(Path(self.input_path).suffix, self.target_ext, sidecar)

    def validate(self) -> None:
        super().validate()
        if self.target_ext not in VIDEO_TARGETS + AUDIO_TARGETS:
            raise _unsupported(self.target_ext)
        outputs = [Path(self.output_path)]
        if self.extract_audio:
            if self.audio_format not in SEPARATOR_FORMATS:
                raise InputError(
                    f"รูปแบบเสียง .{self.audio_format} ไม่รองรับในโหมดแยกเสียง (รองรับเฉพาะ MP3 / WAV)"
                )
            outputs.append(self.audio_output_path)
        if any(_same_file(self.input_path, out) for out in outputs):
            raise InputError("ไฟล์ปลายทางซ้ำกับไฟล์ต้นทาง ระบบไม่เขียนทับต้นฉบับ")

    def process(self) -> Path:
        duration = probe_duration(self.input_path)
        final = Path(self.output_path)

        part = self.partial_output()
        stages = [(
            final, part, build_convert_args(self.input_path, str(part), self.target_ext),
            "กำลังแปลงไฟล์", self.target_ext in AUDIO_TARGETS,
        )]
        sidecar = self.audio_output_path
        if sidecar is not None:
            side_part = self.register_temp(sidecar.with_name(sidecar.name + ".part"))
            stages.append((
                sidecar, side_part,
                build_extract_args(self.input_path, str(side_part), self.audio_format),
                "กำลังแยกเสียง", True,
            ))

        try:
            final.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise InputError(f"สร้างโฟลเดอร์ปลายทางไม่ได้: {exc}") from exc

        total = len(stages)
        for index, (_, _, args, message, audio_only) in enumerate(stages):
            self.check_cancelled()
            low, high = 100 * index / total, 100 * (index + 1) / total
            self.report_progress(low, message)
            self._run_stage(args, duration, low, high, message, audio_only)

        # Publish only after every stage succeeded, so a failure never leaves half a result.
        for destination, partial, *_ in stages:
            try:
                partial.replace(destination)
            except OSError as exc:
                raise ToolFailedError(f"บันทึกไฟล์ปลายทางไม่สำเร็จ: {exc}") from exc
        return final

    def _run_stage(
        self, args: list[str], duration: float, low: float, high: float,
        message: str, audio_only: bool,
    ) -> None:
        try:
            run_ffmpeg(
                args,
                duration=duration,
                on_progress=lambda fraction: self.report_progress(
                    low + fraction * (high - low), message
                ),
                is_cancelled=self.is_cancel_requested,
            )
        except ToolFailedError as exc:
            text = f"{exc}\n{exc.stderr}"
            if audio_only and ("matches no streams" in text or "does not contain any stream" in text):
                raise ToolFailedError("ไฟล์นี้ไม่มีสตรีมเสียงให้แยก") from exc
            raise
