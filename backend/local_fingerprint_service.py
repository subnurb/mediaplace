"""Local audio fingerprinting — Dejavu-inspired, stored in its own DB table.

Computes a compact fingerprint from spectrogram peak constellations (the
same technique Dejavu uses) without requiring MySQL.  Results live in the
`local_fingerprints` table (api.models.LocalFingerprint).

Dependencies
------------
* numpy  — already required by librosa / the rest of the project
* ffmpeg — already installed for yt-dlp; handles all audio formats (MP3, etc.)
           without depending on libsndfile or audioread

No librosa is used here — librosa pulls in numba/LLVM which can fail to load
shared objects on some platforms.  The STFT is implemented directly with numpy.

Public API
----------
compute_fingerprint(audio_path)  → dict | None
store_fingerprint(ts_id, audio_path)  → LocalFingerprint | None
similarity(fp_data_a, fp_data_b)  → float   (0.0 – 1.0)
"""

import hashlib
import logging
import os
import shutil
import subprocess

logger = logging.getLogger(__name__)

# Target sample rate for fingerprinting
_SR = 22050

# Max duration to analyse (seconds)
_MAX_DURATION = 120

# STFT parameters
_N_FFT = 4096
_HOP_LENGTH = 512

# Max constellation hashes stored per track (controls DB row size)
_MAX_HASHES = 500

# Minimum dB level for a spectrogram peak to be considered significant
_PEAK_DB_THRESHOLD = -60

# Fan-out: how many forward peaks to pair with each anchor peak
_FAN_VALUE = 5


def _find_ffmpeg() -> str | None:
    """Return the ffmpeg binary path, checking PATH and common locations."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    for candidate in (
        "/usr/local/bin/ffmpeg",
        "/opt/homebrew/bin/ffmpeg",
        "/usr/bin/ffmpeg",
        os.path.expanduser("~/.local/bin/ffmpeg"),
    ):
        if os.path.isfile(candidate):
            return candidate
    return None


def _load_audio_ffmpeg(audio_path: str):
    """Decode audio to mono float32 numpy array via ffmpeg.

    Returns (samples, sample_rate) or None on failure.
    Using ffmpeg directly avoids libsndfile / audioread / numba dependencies.
    """
    try:
        import numpy as np
    except ImportError:
        return None

    ffmpeg_bin = _find_ffmpeg()
    if not ffmpeg_bin:
        logger.warning("[local_fp] ffmpeg not found — cannot compute fingerprint")
        return None

    cmd = [
        ffmpeg_bin,
        "-i", audio_path,
        "-ar", str(_SR),
        "-ac", "1",
        "-t", str(_MAX_DURATION),
        "-f", "f32le",
        "-",
    ]
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        logger.warning("[local_fp] ffmpeg timed out on %s", audio_path)
        return None
    except Exception as exc:
        logger.warning("[local_fp] ffmpeg error for %s: %s", audio_path, exc)
        return None

    if not proc.stdout:
        err = proc.stderr.decode(errors="replace")[:200] if proc.stderr else ""
        logger.warning("[local_fp] ffmpeg produced no output for %s: %s", audio_path, err)
        return None

    samples = np.frombuffer(proc.stdout, dtype=np.float32).copy()
    return samples, _SR


def _stft_magnitude_db(y, n_fft: int = _N_FFT, hop_length: int = _HOP_LENGTH):
    """Compute STFT magnitude spectrogram in dB using pure numpy.

    Returns a 2-D array of shape (n_fft//2+1, n_frames) in dB.
    Reference is the maximum magnitude value.
    """
    import numpy as np

    window = np.hanning(n_fft).astype(np.float32)
    n_frames = max(1, 1 + (len(y) - n_fft) // hop_length)
    n_bins = n_fft // 2 + 1
    S = np.empty((n_bins, n_frames), dtype=np.float32)

    for i in range(n_frames):
        start = i * hop_length
        frame = y[start: start + n_fft]
        if len(frame) < n_fft:
            frame = np.pad(frame, (0, n_fft - len(frame)))
        S[:, i] = np.abs(np.fft.rfft(frame * window))

    # Convert to dB (reference = max)
    max_val = S.max()
    if max_val > 0:
        S = 20.0 * np.log10(np.maximum(S / max_val, 1e-10))
    else:
        S[:] = -100.0
    return S


def compute_fingerprint(audio_path: str) -> dict | None:
    """Return {fingerprint_hash, fingerprint_data, duration_s} or None on error.

    Algorithm (Dejavu-compatible):
    1. Decode audio via ffmpeg → mono float32 PCM at 22 050 Hz (up to 120 s).
    2. Compute STFT → magnitude spectrogram in dB (pure numpy, no librosa).
    3. For every other time frame, pick the loudest frequency in each of
       10 equal-width frequency bands (only if > -60 dB).
    4. For every peak, pair it with the next _FAN_VALUE peaks and hash the
       triple (freq_anchor, freq_neighbour, time_delta).
    5. Store sorted unique hashes as fingerprint_data; SHA-256 of that list
       as fingerprint_hash.
    """
    try:
        import numpy as np
    except ImportError:
        logger.debug("[local_fp] numpy not installed — skipping")
        return None

    try:
        audio = _load_audio_ffmpeg(audio_path)
        if audio is None:
            return None
        y, sr = audio
        duration_s = float(len(y) / sr)

        # Magnitude spectrogram in dB
        S = _stft_magnitude_db(y)
        n_freq, n_time = S.shape
        band_size = max(1, n_freq // 10)

        # Peak picking: one peak per band per time frame (stride 2)
        peaks = []
        for t in range(0, n_time, 2):
            for b in range(10):
                f_start = b * band_size
                f_end = min(f_start + band_size, n_freq)
                band = S[f_start:f_end, t]
                if band.size == 0:
                    continue
                local_idx = int(np.argmax(band))
                if float(band[local_idx]) > _PEAK_DB_THRESHOLD:
                    peaks.append((t, f_start + local_idx))

        # Constellation hashing: pair each peak with _FAN_VALUE forward peaks
        hashes = []
        for i, (t1, f1) in enumerate(peaks):
            for j in range(1, _FAN_VALUE + 1):
                if i + j >= len(peaks):
                    break
                t2, f2 = peaks[i + j]
                dt = t2 - t1
                if 0 < dt <= 50:
                    h = hashlib.sha1(f"{f1}:{f2}:{dt}".encode()).hexdigest()[:8]
                    hashes.append(h)

        unique_hashes = sorted(set(hashes))
        master_hash = hashlib.sha256(":".join(unique_hashes).encode()).hexdigest()

        return {
            "fingerprint_hash": master_hash,
            "fingerprint_data": unique_hashes[:_MAX_HASHES],
            "duration_s": duration_s,
        }

    except Exception as exc:
        logger.warning("[local_fp] error computing fingerprint for %s: %s", audio_path, exc)
        return None


def store_fingerprint(ts_id: int, audio_path: str):
    """Compute and persist a LocalFingerprint for the given TrackSource id.

    Returns the LocalFingerprint instance (created or updated) or None on failure.
    """
    from api.models import LocalFingerprint, TrackSource

    fp_data = compute_fingerprint(audio_path)
    if not fp_data:
        return None

    try:
        ts = TrackSource.objects.get(id=ts_id)
    except TrackSource.DoesNotExist:
        logger.warning("[local_fp] TrackSource %s not found", ts_id)
        return None

    local_fp, _ = LocalFingerprint.objects.update_or_create(
        track_source=ts,
        defaults={
            "fingerprint_hash": fp_data["fingerprint_hash"],
            "fingerprint_data": fp_data["fingerprint_data"],
            "duration_s": fp_data["duration_s"],
        },
    )
    logger.debug(
        "[local_fp] stored ts=%s hash=%s…  hashes=%d",
        ts_id, fp_data["fingerprint_hash"][:12], len(fp_data["fingerprint_data"]),
    )
    return local_fp


def similarity(fp_data_a: list, fp_data_b: list) -> float:
    """Jaccard similarity between two fingerprint hash lists (0.0 – 1.0).

    A value above ~0.15 strongly suggests the same recording.
    """
    if not fp_data_a or not fp_data_b:
        return 0.0
    set_a = set(fp_data_a)
    set_b = set(fp_data_b)
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0
