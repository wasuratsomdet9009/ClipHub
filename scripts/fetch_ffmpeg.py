"""Download pinned static FFmpeg/ffprobe builds into bin/ for packaging (owner: member 3).

Developer and CI tooling, so messages are English (Windows CI consoles are not always UTF-8).
Usage: python scripts/fetch_ffmpeg.py [--allow-gpl] [--force]
"""
from __future__ import annotations

import argparse
import hashlib
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = ROOT / "bin"
PLACEHOLDER = "SET-ME"

# TEAM DECISION REQUIRED before the first release build. Replace each PLACEHOLDER with a pinned
# https URL of a static build and the SHA256 of that exact archive. Several archives per platform
# are allowed (some sites ship ffmpeg and ffprobe as separate zips). An LGPL build is recommended
# (SRS 5.3.3), but libx264 is GPL: CompressTask needs it, so see the team plan PDF.
SOURCES: dict[str, list[dict[str, str]]] = {
    "windows": [{"url": PLACEHOLDER, "sha256": PLACEHOLDER}],
    "macos-arm64": [{"url": PLACEHOLDER, "sha256": PLACEHOLDER}],
    "macos-x86_64": [{"url": PLACEHOLDER, "sha256": PLACEHOLDER}],
}


def platform_key() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos-arm64" if platform.machine().lower() in ("arm64", "aarch64") else "macos-x86_64"
    raise SystemExit(f"fetch_ffmpeg: unsupported platform {sys.platform!r} (Windows and macOS only)")


def check_pinned(key: str, sources: list[dict[str, str]]) -> None:
    for source in sources:
        url, digest = source.get("url", PLACEHOLDER), source.get("sha256", PLACEHOLDER)
        if PLACEHOLDER in (url, digest):
            raise SystemExit(
                f"fetch_ffmpeg: no pinned FFmpeg source for {key!r}. Edit SOURCES in "
                "scripts/fetch_ffmpeg.py with a real URL and SHA256 (the team must choose the source and licence)."
            )
        if not url.startswith("https://") or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
            raise SystemExit(f"fetch_ffmpeg: {key!r} needs an https URL and a 64-hex SHA256, got {url!r}")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, target: Path) -> None:
    print(f"fetch_ffmpeg: downloading {url}")
    with urllib.request.urlopen(url, timeout=120) as response, target.open("wb") as out:
        shutil.copyfileobj(response, out)


def extract_tools(archive: Path, dest: Path, names: set[str]) -> set[str]:
    """Copy files whose basename is in `names` out of a .zip/.tar.* to dest (flat). Returns names found."""
    found: set[str] = set()
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            for member in zf.namelist():
                base = Path(member).name
                if base in names and not member.endswith("/"):
                    with zf.open(member) as src, (dest / base).open("wb") as out:
                        shutil.copyfileobj(src, out)
                    found.add(base)
    else:
        with tarfile.open(archive) as tf:
            for member in tf.getmembers():
                base = Path(member.name).name
                if base in names and member.isfile():
                    src = tf.extractfile(member)
                    if src is not None:
                        with src, (dest / base).open("wb") as out:
                            shutil.copyfileobj(src, out)
                        found.add(base)
    return found


def inspect_build(ffmpeg: Path, allow_gpl: bool) -> None:
    """Fail loudly on builds we cannot ship or that CompressTask cannot use."""
    version = subprocess.run([str(ffmpeg), "-version"], capture_output=True, text=True, check=True).stdout
    encoders = subprocess.run([str(ffmpeg), "-hide_banner", "-encoders"], capture_output=True, text=True, check=True).stdout
    print(version.splitlines()[0])
    if "--enable-nonfree" in version:
        raise SystemExit("fetch_ffmpeg: this build is --enable-nonfree and cannot be redistributed")
    if "--enable-gpl" in version:
        if not allow_gpl:
            raise SystemExit("fetch_ffmpeg: GPL build. SRS 5.3.3 asks for LGPL; pass --allow-gpl once the team accepts GPL")
        print("fetch_ffmpeg: WARNING GPL build accepted (--allow-gpl)")
    else:
        print("fetch_ffmpeg: LGPL build")
    if not re.search(r"\blibx264\b", encoders) or not re.search(r"\baac\b", encoders):
        raise SystemExit("fetch_ffmpeg: build lacks libx264 or aac, which CompressTask (-c:v libx264 -c:a aac) needs")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-gpl", action="store_true", help="accept a GPL FFmpeg build (needed for libx264)")
    parser.add_argument("--force", action="store_true", help="download again even if bin/ is already filled")
    args = parser.parse_args(argv)

    key = platform_key()
    suffix = ".exe" if key == "windows" else ""
    wanted = {f"ffmpeg{suffix}", f"ffprobe{suffix}"}
    sources = SOURCES.get(key, [])
    check_pinned(key, sources)

    if not args.force and all((BIN_DIR / name).is_file() for name in wanted):
        print(f"fetch_ffmpeg: bin/ already has {sorted(wanted)}; use --force to replace")
    else:
        BIN_DIR.mkdir(exist_ok=True)
        found: set[str] = set()
        with tempfile.TemporaryDirectory() as tmp:
            for index, source in enumerate(sources):
                archive = Path(tmp) / f"ffmpeg-{index}.archive"
                download(source["url"], archive)
                actual = sha256_of(archive)
                if actual.lower() != source["sha256"].lower():
                    raise SystemExit(f"fetch_ffmpeg: SHA256 mismatch for {source['url']}: got {actual}")
                found |= extract_tools(archive, BIN_DIR, wanted)
        if found != wanted:
            raise SystemExit(f"fetch_ffmpeg: archives did not contain {sorted(wanted - found)}")
        for name in wanted:
            (BIN_DIR / name).chmod(0o755)

    inspect_build(BIN_DIR / f"ffmpeg{suffix}", args.allow_gpl)
    print(f"fetch_ffmpeg: ready in {BIN_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

