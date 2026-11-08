"""Error types shared by all tasks. Each message is user-facing Thai text."""
from __future__ import annotations


class ClipHubError(Exception):
    """Base class. str(exc) is shown to the user as-is."""


class InputError(ClipHubError):
    """Input file or URL is missing, unreadable or invalid."""


class ToolNotFoundError(ClipHubError):
    """FFmpeg / ffprobe / yt-dlp cannot be located."""


class ToolFailedError(ClipHubError):
    """An external process exited with an error. `stderr` keeps the raw tool output."""

    def __init__(self, message: str, stderr: str = "") -> None:
        super().__init__(message)
        self.stderr = stderr


class TaskCancelledError(ClipHubError):
    """Raised inside a task when the user cancels it."""
