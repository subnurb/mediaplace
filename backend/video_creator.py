import math
import subprocess
import os
import tempfile

import numpy as np
from PIL import Image, ImageDraw

from ffmpeg_utils import find_ffmpeg

# Video settings
WIDTH, HEIGHT = 1920, 1080
FPS = 30


def _create_circle_mask(size):
    """Create a circular alpha mask."""
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size - 1, size - 1), fill=255)
    return mask


def _crop_circle(img):
    """Crop an image into a circle with transparent background."""
    size = min(img.width, img.height)
    # Center crop to square
    left = (img.width - size) // 2
    top = (img.height - size) // 2
    img = img.crop((left, top, left + size, top + size))
    img = img.convert("RGBA")

    mask = _create_circle_mask(size)
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(img, (0, 0), mask)
    return result


def _compute_beat_envelope(audio_path, total_frames):
    """Analyze audio beats and return a per-frame scale envelope."""
    import librosa

    y, sr = librosa.load(audio_path, sr=22050, mono=True)
    duration = len(y) / sr

    # Onset strength for pulse intensity
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    onset_times = librosa.times_like(onset_env, sr=sr)

    # Beat tracking
    tempo, beat_frames_lib = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames_lib, sr=sr)

    # Build per-video-frame scale values
    scales = np.ones(total_frames)
    pulse_strength = 0.10  # 10% max scale increase
    decay_frames = int(FPS * 0.15)  # Pulse decays over 150ms

    for bt in beat_times:
        frame_idx = int(bt * FPS)
        # Find onset strength at this beat
        closest = np.argmin(np.abs(onset_times - bt))
        intensity = min(onset_env[closest] / (np.max(onset_env) + 1e-6), 1.0)

        for d in range(decay_frames + 1):
            fi = frame_idx + d
            if fi >= total_frames:
                break
            # Exponential decay
            t = d / max(decay_frames, 1)
            pulse = pulse_strength * intensity * math.exp(-4 * t)
            scales[fi] = max(scales[fi], 1.0 + pulse)

    return scales, duration


def _render_circle_pulse_frames(image_path, audio_path, frames_dir):
    """Render individual frames with circle-cropped pulsing image."""
    # Load and prepare circle image
    img = Image.open(image_path)
    circle_img = _crop_circle(img)

    # Base size: fit circle in frame with margin
    base_size = int(min(WIDTH, HEIGHT) * 0.55)
    max_size = int(base_size * 1.12)  # Room for pulse

    # Pre-scale circle to max size (we'll scale down per frame)
    circle_hq = circle_img.resize((max_size, max_size), Image.LANCZOS)

    # Get audio duration to compute total frames
    import librosa
    y, sr = librosa.load(audio_path, sr=22050, mono=True, duration=5)
    # Get full duration without loading all audio again
    duration = librosa.get_duration(path=audio_path)
    total_frames = int(duration * FPS) + 1

    # Compute beat envelope
    scales, _ = _compute_beat_envelope(audio_path, total_frames)

    # Black background
    bg = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 255))

    for i in range(total_frames):
        frame = bg.copy()

        # Scale the circle
        current_size = int(base_size * scales[i])
        if current_size % 2 != 0:
            current_size += 1

        scaled = circle_hq.resize((current_size, current_size), Image.LANCZOS)

        # Center on frame
        x = (WIDTH - current_size) // 2
        y_pos = (HEIGHT - current_size) // 2

        frame.paste(scaled, (x, y_pos), scaled)

        # Save as RGB (no alpha for video)
        frame_rgb = frame.convert("RGB")
        frame_rgb.save(os.path.join(frames_dir, f"frame_{i:06d}.png"))

    return total_frames


def create_video(image_path, audio_path, output_path, animation="none"):
    """Create a video from an image and audio file.

    animation: "none" for static image, "circle_pulse" for beat-synced pulsing circle.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    ffmpeg = find_ffmpeg()

    if animation == "circle_pulse":
        _create_circle_pulse_video(image_path, audio_path, output_path, ffmpeg)
    else:
        _create_static_video(image_path, audio_path, output_path, ffmpeg)

    return output_path


def _create_static_video(image_path, audio_path, output_path, ffmpeg):
    """Original static image video."""
    cmd = [
        ffmpeg,
        "-y",
        "-loop", "1",
        "-i", image_path,
        "-i", audio_path,
        "-vf", f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
               f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black",
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed:\n{result.stderr}")


def _create_circle_pulse_video(image_path, audio_path, output_path, ffmpeg):
    """Render circle-cropped pulsing video synced to beats."""
    with tempfile.TemporaryDirectory() as frames_dir:
        total_frames = _render_circle_pulse_frames(image_path, audio_path, frames_dir)

        # Combine frames + audio with FFmpeg
        frames_pattern = os.path.join(frames_dir, "frame_%06d.png")
        cmd = [
            ffmpeg,
            "-y",
            "-framerate", str(FPS),
            "-i", frames_pattern,
            "-i", audio_path,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            output_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed:\n{result.stderr}")
