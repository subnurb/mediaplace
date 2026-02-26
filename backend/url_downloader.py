import os
import re
import subprocess
import json
import urllib.request

from ffmpeg_utils import find_ffmpeg_dir


def detect_platform(url):
    """Detect the music platform from a URL."""
    if "soundcloud.com" in url:
        return "soundcloud"
    if "spotify.com" in url:
        return "spotify"
    if "deezer.com" in url:
        return "deezer"
    if "music.youtube.com" in url or "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    return "unknown"


def _find_yt_dlp():
    """Find yt-dlp executable."""
    import shutil
    path = shutil.which("yt-dlp")
    if path:
        return path
    raise FileNotFoundError(
        "yt-dlp not found. Install it with: pip install yt-dlp"
    )


def _get_soundcloud_hq_cover(thumbnail_url):
    """Get the highest quality cover image URL from SoundCloud.

    SoundCloud thumbnail URLs contain size tokens like t120x120, t200x200, etc.
    Replace with t500x500 (max) or original for best quality.
    """
    if not thumbnail_url:
        return thumbnail_url

    # Try t500x500 first (highest standard size), then original
    hq_url = re.sub(r'-t\d+x\d+', '-t500x500', thumbnail_url)
    if hq_url != thumbnail_url:
        return hq_url

    # Also handle /artworks-... pattern
    hq_url = re.sub(r'(artworks-\w+)-\w+(\.\w+)', r'\1-t500x500\2', thumbnail_url)
    if hq_url != thumbnail_url:
        return hq_url

    return thumbnail_url


def _download_image(url, output_path):
    """Download an image, trying the URL as-is first, then falling back."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response:
            with open(output_path, "wb") as f:
                f.write(response.read())
        # Verify the file is non-empty
        if os.path.getsize(output_path) > 0:
            return output_path
    except Exception:
        pass

    # Remove the file if it was created but empty/invalid
    if os.path.exists(output_path):
        os.remove(output_path)
    return None


def download_from_url(url, output_dir):
    """Download audio and cover image from a music platform URL.

    Returns a dict with keys: audio_path, image_path, title, description, platform
    """
    platform = detect_platform(url)
    yt_dlp = _find_yt_dlp()
    ffmpeg_dir = find_ffmpeg_dir()

    os.makedirs(output_dir, exist_ok=True)

    # Extract metadata (title, thumbnail, etc.)
    meta_cmd = [
        yt_dlp,
        "--ffmpeg-location", ffmpeg_dir,
        "--dump-json",
        "--no-download",
        url,
    ]
    meta_result = subprocess.run(meta_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if meta_result.returncode != 0:
        raise RuntimeError(f"Failed to fetch metadata from {platform}: {meta_result.stderr}")

    metadata = json.loads(meta_result.stdout)
    title = metadata.get("title", "Untitled")
    uploader = metadata.get("uploader", "")
    description = metadata.get("description", "")
    thumbnail_url = metadata.get("thumbnail", "")

    # Sanitize title for filename
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:80]

    # --- Download audio in best quality ---
    audio_template = os.path.join(output_dir, f"{safe_title}.%(ext)s")

    if platform == "soundcloud":
        # SoundCloud: prefer original format, best quality
        audio_cmd = [
            yt_dlp,
            "--ffmpeg-location", ffmpeg_dir,
            "-f", "bestaudio",            # Best audio stream available
            "-x",                          # Extract audio
            "--audio-format", "mp3",       # Convert to mp3
            "--audio-quality", "0",        # Best VBR quality (V0 ~245kbps)
            "--no-playlist",
            "-o", audio_template,
            url,
        ]
    else:
        audio_cmd = [
            yt_dlp,
            "--ffmpeg-location", ffmpeg_dir,
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "-o", audio_template,
            url,
        ]

    audio_result = subprocess.run(audio_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if audio_result.returncode != 0:
        raise RuntimeError(f"Failed to download audio: {audio_result.stderr}")

    # Find the downloaded audio file
    final_audio = os.path.join(output_dir, f"{safe_title}.mp3")
    if not os.path.exists(final_audio):
        for f in os.listdir(output_dir):
            if f.startswith(safe_title) and not f.endswith(('.jpg', '.png', '.webp')):
                final_audio = os.path.join(output_dir, f)
                break

    if not os.path.exists(final_audio):
        raise RuntimeError("Audio download completed but file not found.")

    # --- Download cover image ---
    image_path = os.path.join(output_dir, f"{safe_title}_cover.jpg")

    if platform == "soundcloud" and thumbnail_url:
        # Get highest quality SoundCloud cover
        hq_thumbnail = _get_soundcloud_hq_cover(thumbnail_url)

        # Try HQ first, fall back to original thumbnail
        downloaded = _download_image(hq_thumbnail, image_path)
        if not downloaded and hq_thumbnail != thumbnail_url:
            downloaded = _download_image(thumbnail_url, image_path)
        if not downloaded:
            image_path = None

        # Also try thumbnails list for even higher res
        if not image_path:
            for thumb in metadata.get("thumbnails", []):
                thumb_url = thumb.get("url", "")
                if thumb_url:
                    hq = _get_soundcloud_hq_cover(thumb_url)
                    downloaded = _download_image(hq, os.path.join(output_dir, f"{safe_title}_cover.jpg"))
                    if downloaded:
                        image_path = downloaded
                        break
    elif thumbnail_url:
        downloaded = _download_image(thumbnail_url, image_path)
        if not downloaded:
            image_path = None
    else:
        image_path = None

    # --- Fallback 1: extract embedded art from the MP3 via FFmpeg ---
    if not image_path and os.path.exists(final_audio):
        extracted = os.path.join(output_dir, f"{safe_title}_cover_extracted.jpg")
        try:
            ffmpeg_bin = os.path.join(ffmpeg_dir, "ffmpeg")
            r = subprocess.run(
                [ffmpeg_bin, "-y", "-i", final_audio, "-an", "-vcodec", "copy", extracted],
                capture_output=True,
            )
            if r.returncode == 0 and os.path.exists(extracted) and os.path.getsize(extracted) > 0:
                image_path = extracted
        except Exception:
            pass

    # --- Fallback 2: black 500×500 placeholder so the upload can proceed ---
    if not image_path:
        placeholder = os.path.join(output_dir, f"{safe_title}_cover_placeholder.jpg")
        try:
            from PIL import Image as _Image
            _Image.new("RGB", (500, 500), (0, 0, 0)).save(placeholder, "JPEG")
            image_path = placeholder
        except Exception:
            pass

    return {
        "audio_path": final_audio,
        "image_path": image_path,
        "title": title,
        "uploader": uploader,
        "description": description,
        "platform": platform,
    }
