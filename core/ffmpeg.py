"""FFmpeg / ffprobe helpers shared by Features 2-4.

find_tool() prefers a copy bundled with the app (bin/ in the repo during
development, or the PyInstaller bundle) and falls back to PATH.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from core.errors import TaskCancelledError, ToolFailedError, ToolNotFoundError


def _bundle_root() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    return Path(meipass) if meipass else Path(__file__).resolve().parent.parent


def _spawn_kwargs() -> dict[str, Any]:
    """No stdin and no console window flash when the packaged GUI app starts a tool."""
    kwargs: dict[str, Any] = {"stdin": subprocess.DEVNULL}
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return kwargs


# A macOS app started from Finder or the Dock does not inherit the shell PATH,
# so Homebrew installs are invisible unless their folders are checked directly.
_EXTRA_DIRS = ("/opt/homebrew/bin", "/usr/local/bin")


def find_tool(name: str) -> str:
    exe = f"{name}.exe" if sys.platform == "win32" else name
    bundled = _bundle_root() / "bin" / exe
    if bundled.is_file():
        return str(bundled)
    found = shutil.which(name)
    if found is None:
        for directory in _EXTRA_DIRS:
            candidate = Path(directory) / exe
            if candidate.is_file():
                return str(candidate)
        raise ToolNotFoundError(f"ไม่พบโปรแกรม {name} กรุณาติดตั้ง FFmpeg ก่อนใช้งาน")
    return found


def probe_format(path: str) -> dict[str, Any]:
    """ffprobe's 'format' block: duration (str, seconds), bit_rate, size, format_name."""
    cmd = [
        find_tool("ffprobe"), "-v", "error",
        "-show_entries", "format=duration,bit_rate,size,format_name",
        "-of", "json", path,
    ]
    proc = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False, **_spawn_kwargs(),
    )
    try:
        return json.loads(proc.stdout)["format"]
    except (KeyError, json.JSONDecodeError) as exc:
        raise ToolFailedError("อ่านข้อมูลไฟล์ไม่ได้ ไฟล์อาจเสียหาย") from exc


def probe_duration(path: str) -> float:
    try:
        duration = float(probe_format(path).get("duration") or 0)
    except ValueError as exc:
        raise ToolFailedError("ไม่พบความยาวของไฟล์") from exc
    if duration <= 0:
        raise ToolFailedError("ไม่พบความยาวของไฟล์")
    return duration


def run_ffmpeg(
    args: Sequence[str],
    *,
    duration: float,
    on_progress: Callable[[float], None] | None = None,
    is_cancelled: Callable[[], bool] = lambda: False,
) -> None:
    """Run ffmpeg with the given input/output options. Progress is reported as 0.0-1.0.

    Output muxer should be given explicitly with -f, because temp names end in .part.
    Raises TaskCancelledError (after killing ffmpeg) when is_cancelled() returns True,
    and ToolFailedError (message = last ffmpeg error line, .stderr = all of it) on a non-zero exit.
    """
    cmd = [
        find_tool("ffmpeg"), "-hide_banner", "-nostdin", "-y",
        "-loglevel", "error", "-nostats", "-progress", "pipe:1",
        *args,
    ]
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", **_spawn_kwargs(),
        )
    except OSError as exc:
        raise ToolNotFoundError(f"เรียกใช้ FFmpeg ไม่ได้: {exc}") from exc

    # Drain stderr on a thread: a corrupt input can print enough errors to fill the pipe
    # and block ffmpeg while we are still reading progress from stdout.
    stderr_parts: list[str] = []
    drain = threading.Thread(
        target=lambda: stderr_parts.append(proc.stderr.read()), daemon=True
    )
    drain.start()
    seen_us = False
    try:
        for line in proc.stdout:
            if is_cancelled():
                raise TaskCancelledError("ยกเลิกงานแล้ว")
            key, _, value = line.strip().partition("=")
            seen_us = seen_us or key == "out_time_us"
            # out_time_ms is misnamed (also microseconds); only older builds lack out_time_us
            wanted = key == "out_time_us" or (key == "out_time_ms" and not seen_us)
            if wanted and duration > 0 and on_progress is not None:
                try:
                    seconds = int(value) / 1_000_000
                except ValueError:
                    continue
                on_progress(max(0.0, min(seconds / duration, 1.0)))
        proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        drain.join(timeout=5)
        for pipe in (proc.stdout, proc.stderr):
            if pipe is not None:
                pipe.close()

    if proc.returncode != 0:
        stderr = "".join(stderr_parts).strip()
        lines = stderr.splitlines()
        last = lines[-1] if lines else "ไม่ทราบสาเหตุ"
        raise ToolFailedError(f"FFmpeg ทำงานไม่สำเร็จ: {last}", stderr=stderr)
