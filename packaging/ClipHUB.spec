# PyInstaller spec for ClipHUB. Run from the repo root: pyinstaller --noconfirm packaging/ClipHUB.spec
# Windows -> dist/ClipHUB.exe (single file). macOS -> dist/ClipHUB.app (folder bundle, packed into a .dmg by CI).
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).parent  # SPECPATH is the folder that contains this spec file
SUFFIX = ".exe" if sys.platform == "win32" else ""

# FFmpeg is bundled only when scripts/fetch_ffmpeg.py has put it in bin/, so dev builds still work.
ffmpeg_tools = [ROOT / "bin" / f"{name}{SUFFIX}" for name in ("ffmpeg", "ffprobe")]
binaries = [(str(path), "bin") for path in ffmpeg_tools if path.is_file()]

# Unverified: not yet run on real Windows/macOS runners. yt-dlp loads extractors dynamically; the AI stack
# ships native libraries and a VAD model file. Trim a package if the first CI build shows it is unnecessary.
datas = []
hiddenimports = collect_submodules("yt_dlp")
for package in ("faster_whisper", "ctranslate2", "onnxruntime", "av"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter"],
)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ClipHUB", console=False)
    coll = COLLECT(exe, a.binaries, a.datas, name="ClipHUB")
    app = BUNDLE(
        coll,
        name="ClipHUB.app",
        bundle_identifier="com.cliphub.app",
        info_plist={"NSHighResolutionCapable": True},
    )
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="ClipHUB", console=False, upx=False)
