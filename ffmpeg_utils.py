import glob
import os
import shutil


def find_ffmpeg():
    """Find ffmpeg executable, checking PATH and common install locations."""
    path = shutil.which("ffmpeg")
    if path:
        return path

    # Check WinGet install location
    winget_pattern = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Microsoft", "WinGet", "Packages", "*ffmpeg*", "**", "ffmpeg.exe",
    )
    matches = glob.glob(winget_pattern, recursive=True)
    if matches:
        return matches[0]

    raise FileNotFoundError(
        "FFmpeg not found. Install it with: winget install FFmpeg  "
        "then restart your terminal (or add it to PATH)."
    )


def find_ffmpeg_dir():
    """Return the directory containing ffmpeg (for --ffmpeg-location)."""
    return os.path.dirname(find_ffmpeg())
