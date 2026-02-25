import glob
import os
import shutil
import sys


def find_ffmpeg():
    """Find ffmpeg executable, checking PATH and common install locations."""
    path = shutil.which("ffmpeg")
    if path:
        return path

    if sys.platform == "darwin":
        # Homebrew install locations (Intel and Apple Silicon)
        for candidate in [
            "/usr/local/bin/ffmpeg",
            "/opt/homebrew/bin/ffmpeg",
        ]:
            if os.path.isfile(candidate):
                return candidate

    elif sys.platform == "win32":
        # WinGet install location
        winget_pattern = os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            "Microsoft", "WinGet", "Packages", "*ffmpeg*", "**", "ffmpeg.exe",
        )
        matches = glob.glob(winget_pattern, recursive=True)
        if matches:
            return matches[0]

    elif sys.platform.startswith("linux"):
        for candidate in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
            if os.path.isfile(candidate):
                return candidate

    if sys.platform == "darwin":
        install_hint = "brew install ffmpeg"
    elif sys.platform == "win32":
        install_hint = "winget install FFmpeg"
    else:
        install_hint = "sudo apt install ffmpeg  (or your distro's equivalent)"

    raise FileNotFoundError(
        f"FFmpeg not found. Install it with: {install_hint}  "
        "then restart your terminal (or add it to PATH)."
    )


def find_ffmpeg_dir():
    """Return the directory containing ffmpeg (for --ffmpeg-location)."""
    return os.path.dirname(find_ffmpeg())
