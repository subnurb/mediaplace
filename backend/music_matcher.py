"""Cross-platform music track matching.

Strategy:
  Level 1 — Metadata matching
    • Normalize title/artist preserving Unicode (NFKD fold, no ASCII strip)
    • _clean_title: remove "Artist - " prefix common in YouTube uploads
    • _build_queries: multiple query formulations for better recall
    • Search YouTube with ytsearch n=10 (ytmsearch scheme is broken in yt-dlp 2026+)
    • Score: title 45% + artist 35% + duration 20%
    • ISRC exact match → instant 1.0

  Level 2 — MusicBrainz enrichment (when Level 1 score < THRESHOLD_MATCHED)
    • Fetch canonical title/artist/ISRCs from MusicBrainz via urllib (SSL bypass for macOS)
    • Re-score existing candidates + run fresh searches with canonical metadata
    • Rate-limited: 1 request/second

  Level 3 — Audio feature analysis (optional, caller-driven)
    • analyze_audio_features(path): librosa BPM, key, mode, energy
    • bpm_match_boost(score, src, cand): ±0.05 BPM proximity adjustment

Thresholds:
  >= 0.90  → MATCHED      (high confidence, no review needed)
  0.55–0.90 → UNCERTAIN   (flag for user review)
  < 0.55   → NOT_FOUND    (needs upload)
"""

import re
import ssl
import time
import unicodedata
import urllib.parse
import urllib.request
import json
import logging

import yt_dlp
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

# ── Unicode-aware normalization ────────────────────────────────────────────────

_NOISE_RE = re.compile(
    r"""
    \(official\s*(?:music\s*)?video\)   |
    \(official\s*audio\)                |
    \(official\s*lyric\s*video\)        |
    \(lyric[s]?\s*(?:video)?\)          |
    \(visualizer\)                      |
    \(hd\)                              |
    \(4k\)                              |
    \(remaster(?:ed)?\s*\d*\)           |
    \(live(?:\s+at\s+.+?)?\)            |
    \(acoustic(?:\s+version)?\)         |
    \(radio\s*edit\)                    |
    \(extended\s*(?:mix|version)?\)     |
    \[official\s*(?:music\s*)?video\]   |
    \[remaster(?:ed)?\s*\d*\]           |
    \(prod\.?\s+[^)]+\)                 |
    \[prod\.?\s+[^\]]+\]                |
    ft\.?\s+[\w\s,&]+(?=\s|$)          |
    feat\.?\s+[\w\s,&]+(?=\s|$)        |
    \s*[-–|]\s*(?:official|lyrics?|audio|visualizer|hd|4k).*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

_VEVO_RE = re.compile(
    r"(?i)\s*(vevo|official|music|records?|tv|channel|topic)\s*$"
)

# Handle "artist-name" style SoundCloud permalinks
_SLUG_RE = re.compile(r"[-_]+")


def _fold(s: str) -> str:
    """Unicode case-fold and NFKD decompose. Keeps all scripts (no ASCII strip)."""
    return " ".join(unicodedata.normalize("NFKD", s.casefold()).split())


def normalize_title(s: str) -> str:
    """Strip noise patterns, fold unicode, collapse whitespace."""
    s = _NOISE_RE.sub(" ", s)
    s = re.sub(r"[^\w\s\-]", " ", s)
    return " ".join(_fold(s).split())


def normalize_artist(s: str) -> str:
    """Take only the primary artist (before feat./&), fold unicode."""
    s = re.split(r"\s+(?:feat|ft|featuring|&|,|x)\s+", s, flags=re.IGNORECASE)[0]
    return " ".join(_fold(s).split())


def normalize_yt_channel(channel: str) -> str:
    """Strip YouTube channel noise ('DaftPunkVEVO' → 'daft punk')."""
    channel = _VEVO_RE.sub("", channel)
    return " ".join(_fold(channel).split())


def _clean_title(title: str, artist: str) -> str:
    """Remove artist prefix from YouTube-style 'Artist - Title' format.

    'AURORA - Runaway' → 'Runaway'
    'Daft Punk – Get Lucky' → 'Get Lucky'
    """
    clean = normalize_title(title)
    if not artist:
        return clean
    # Build a pattern matching the folded artist at the start
    folded_artist = re.escape(normalize_artist(artist))
    prefix_re = re.compile(
        rf"^\[?{folded_artist}[\]:]?\s*[-–]\s*",
        re.IGNORECASE,
    )
    stripped = prefix_re.sub("", clean).strip()
    if stripped and stripped.lower() != clean.lower():
        return stripped
    return clean


def _build_queries(title: str, artist: str) -> list:
    """Return deduplicated query strings from most to least specific.

    Always includes the raw (non-normalized) title as a final fallback so that
    special characters preserved by platforms (label codes like [LIP006],
    Unicode symbols like †, colons, etc.) are sent to the search engine as-is.
    These characters are stripped by normalize_title but help YouTube rank
    niche / underground tracks correctly.
    """
    clean = _clean_title(title, artist) if artist else normalize_title(title)
    full_norm = normalize_title(title)

    queries = []
    if artist:
        queries.append(f"{artist} {clean}")   # "AURORA Runaway"
        if full_norm.lower() != clean.lower():
            queries.append(f"{artist} {full_norm}")  # fallback with full normalized title
        queries.append(clean)                  # title-only (normalized)
    else:
        queries.append(full_norm)

    # Raw title — preserves [LIP006], †, colons, etc. that YouTube uses for ranking
    queries.append(title)

    # Deduplicate while preserving order
    seen = set()
    result = []
    for q in queries:
        key = q.lower().strip()
        if key not in seen:
            seen.add(key)
            result.append(q)
    return result


# ── Version mismatch penalty ──────────────────────────────────────────────────

# Words that indicate a specific version of a recording
_VERSION_RE = re.compile(
    r"\b(remix|remixed|live|acoustic|cover|demo|instrumental|karaoke|"
    r"radio\s*edit|extended|reprise|mashup|flip|rework|bootleg|stripped|"
    r"orchestral|piano\s*version|a\s*cappella|unplugged)\b",
    re.IGNORECASE,
)


def _version_penalty(source_title: str, cand_title: str) -> float:
    """Return a penalty when the candidate has version markers the source doesn't.

    Example: source='Runaway', cand='Runaway (Acoustic)' → -0.15
             source='Runaway (Acoustic)', cand='Runaway (Acoustic Version)' → 0.0
    """
    src_versions = set(m.lower() for m in _VERSION_RE.findall(source_title))
    cnd_versions = set(m.lower() for m in _VERSION_RE.findall(cand_title))

    # Normalize "radio edit" / "radio  edit" → same key
    extra = cnd_versions - src_versions
    if extra:
        return -0.15  # fixed penalty — one wrong version marker is enough
    return 0.0


# ── Artist scoring ─────────────────────────────────────────────────────────────

def _artist_score(source_artist: str, cand_artist: str) -> float:
    """Score artist similarity, robust to YouTube channel naming conventions.

    Uses token_set_ratio so that a channel with extra words (e.g. "AURORA - Topic",
    "AURORA Official Music", "Aurora Aksnes") still fully matches a simple artist
    name like "AURORA" — because the source name is a subset of the candidate tokens.

    Also handles compound slugs without separators (e.g. "auroraaksnes" starting
    with "aurora") via a prefix check.
    """
    if not source_artist or not cand_artist:
        return 0.5  # neutral when unknown

    src = normalize_artist(source_artist)
    # Try both raw form and slug-expanded form of candidate
    raw = normalize_yt_channel(cand_artist)
    slug = normalize_yt_channel(_SLUG_RE.sub(" ", cand_artist))

    # token_set_ratio: "aurora" ⊆ {"aurora","topic"} → 100
    # Handles "AURORA - Topic", "Aurora Aksnes", "AURORA Official", etc.
    score_raw = fuzz.token_set_ratio(src, raw) / 100.0
    score_slug = fuzz.token_set_ratio(src, slug) / 100.0
    best = max(score_raw, score_slug)

    # Compound slug check: "auroraaksnes".startswith("aurora") → same artist
    # Handles SoundCloud usernames where full_name was unavailable
    if best < 0.85:
        src_compact = src.replace(" ", "")
        for cand_form in (raw, slug):
            cand_compact = cand_form.replace(" ", "")
            if src_compact and cand_compact:
                overlap = min(len(src_compact), len(cand_compact))
                total = max(len(src_compact), len(cand_compact))
                if (cand_compact.startswith(src_compact)
                        or src_compact.startswith(cand_compact)):
                    # Score by coverage: full overlap ≈ 0.90; half ≈ 0.60
                    best = max(best, 0.50 + 0.40 * overlap / total)

    return best


# ── Duration scoring ───────────────────────────────────────────────────────────

def _duration_score(dur_a_ms, dur_b_sec, tolerance_sec=5):
    """Return 0–1 duration similarity. Both inputs may be None."""
    if not dur_a_ms or not dur_b_sec:
        return None  # unknown → weight redistributed by caller

    dur_a_sec = dur_a_ms / 1000
    diff = abs(dur_a_sec - dur_b_sec)

    if diff <= tolerance_sec:
        return 1.0
    elif diff <= 30:
        return 1.0 - (diff - tolerance_sec) / 30.0
    else:
        return 0.0


# ── Composite score ────────────────────────────────────────────────────────────

def score_candidate(source_title, source_artist, source_duration_ms,
                    cand_title, cand_artist, cand_duration_sec,
                    source_isrc=None, cand_isrc=None):
    """Return a 0–1 match confidence score.

    ISRC exact match short-circuits to 1.0.
    Duration unknown → redistribute its 20% weight to title/artist.
    """
    # ISRC short-circuit
    if source_isrc and cand_isrc:
        if source_isrc.strip().upper() == cand_isrc.strip().upper():
            return 1.0

    # Title: use token_set_ratio to handle word re-ordering and subsets
    t_score = fuzz.token_set_ratio(
        normalize_title(source_title), normalize_title(cand_title)
    ) / 100.0

    a_score = _artist_score(source_artist, cand_artist)
    d_score = _duration_score(source_duration_ms, cand_duration_sec)

    if d_score is None:
        base = t_score * 0.57 + a_score * 0.43
    else:
        base = t_score * 0.45 + a_score * 0.35 + d_score * 0.20

    # Penalise version-type mismatches using the original (non-normalized) titles
    penalty = _version_penalty(source_title, cand_title)
    return max(0.0, min(1.0, base + penalty))


# ── YouTube search via yt-dlp ─────────────────────────────────────────────────

_YDL_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": True,
    "skip_download": True,
}


def _search_youtube(query: str, n=10) -> list:
    """Return up to n raw yt-dlp entry dicts for a query string."""
    with yt_dlp.YoutubeDL(_YDL_OPTS) as ydl:
        try:
            result = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
            return result.get("entries", []) or []
        except Exception as exc:
            logger.debug("yt-dlp search failed for %r: %s", query, exc)
            return []


def _entry_to_candidate(entry: dict) -> dict:
    """Normalise a raw yt-dlp entry into a unified candidate dict."""
    title = entry.get("track") or entry.get("title") or ""
    artist = entry.get("artist") or entry.get("channel") or entry.get("uploader") or ""
    vid = entry.get("id") or ""
    if not vid and entry.get("url"):
        m = re.search(r"[?&]v=([^&]+)", entry["url"])
        vid = m.group(1) if m else entry["url"]
    return {
        "video_id": vid,
        "title": title,
        "artist": artist,
        "duration_sec": entry.get("duration"),
        "url": entry.get("url") or entry.get("webpage_url") or "",
    }


def _collect_candidates(queries: list, n_per_query=10) -> list:
    """Run all queries, return deduplicated candidates by video_id."""
    seen_ids = set()
    candidates = []
    for query in queries:
        for entry in _search_youtube(query, n=n_per_query):
            cand = _entry_to_candidate(entry)
            if cand.get("title") and cand["video_id"] not in seen_ids:
                seen_ids.add(cand["video_id"])
                candidates.append(cand)
    return candidates


def _best_from_candidates(candidates, source_title, source_artist,
                           source_duration_ms, source_isrc=None):
    """Score all candidates and return (best_cand, best_score)."""
    best_score = 0.0
    best = None
    for cand in candidates:
        if not cand.get("title"):
            continue
        score = score_candidate(
            source_title, source_artist, source_duration_ms,
            cand["title"], cand["artist"], cand["duration_sec"],
            source_isrc=source_isrc,
        )
        if score > best_score:
            best_score = score
            best = cand
    return best, best_score


def _rank_all_candidates(candidates, source_title, source_artist,
                          source_duration_ms, source_isrc=None, min_score=0.0) -> list:
    """Score all candidates and return them sorted by confidence desc.

    Returns a list of dicts: {video_id, title, artist, confidence}.
    Candidates below min_score are excluded.
    """
    scored = []
    for cand in candidates:
        if not cand.get("title") or not cand.get("video_id"):
            continue
        conf = score_candidate(
            source_title, source_artist, source_duration_ms,
            cand["title"], cand["artist"], cand["duration_sec"],
            source_isrc=source_isrc,
        )
        if conf >= min_score:
            scored.append({
                "video_id": cand["video_id"],
                "title": cand["title"],
                "artist": cand.get("artist", ""),
                "confidence": round(conf, 4),
            })
    return sorted(scored, key=lambda x: x["confidence"], reverse=True)


# ── MusicBrainz enrichment ────────────────────────────────────────────────────

_MB_BASE = "https://musicbrainz.org/ws/2"
_MB_HEADERS = {
    "User-Agent": "MediaplaceApp/1.0 (mediaplace@example.com)",
    "Accept": "application/json",
}
_mb_last_request = 0.0


def _mb_get(path: str, params: dict) -> dict:
    """MusicBrainz GET with rate limiting (1 req/sec) and SSL bypass."""
    global _mb_last_request
    elapsed = time.monotonic() - _mb_last_request
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)

    url = f"{_MB_BASE}{path}?{urllib.parse.urlencode(params)}"
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url, headers=_MB_HEADERS)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            _mb_last_request = time.monotonic()
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logger.debug("MusicBrainz request failed: %s", exc)
        _mb_last_request = time.monotonic()
        return {}


def _mb_lookup(title: str, artist: str) -> tuple:
    """Look up canonical title/artist and ISRCs from MusicBrainz.

    Returns (canonical_title, canonical_artist, [isrc, ...])
    Returns (None, None, []) on failure.
    """
    query_parts = []
    if title:
        clean = _clean_title(title, artist) if artist else normalize_title(title)
        query_parts.append(f'recording:"{clean}"')
    if artist:
        query_parts.append(f'artist:"{normalize_artist(artist)}"')

    if not query_parts:
        return None, None, []

    data = _mb_get("/recording", {
        "query": " AND ".join(query_parts),
        "limit": 5,
        "fmt": "json",
        "inc": "isrcs artist-credits",
    })

    recordings = data.get("recordings", [])
    if not recordings:
        return None, None, []

    # Pick the recording with the best title similarity
    source_norm = normalize_title(clean if title else "")
    best_rec = None
    best_sim = 0.0
    for rec in recordings:
        rec_title = rec.get("title", "")
        sim = fuzz.token_set_ratio(source_norm, normalize_title(rec_title)) / 100.0
        if sim > best_sim:
            best_sim = sim
            best_rec = rec

    if not best_rec or best_sim < 0.6:
        return None, None, []

    canonical_title = best_rec.get("title", "")

    # Extract primary artist name
    canonical_artist = artist  # fallback to input
    artist_credits = best_rec.get("artist-credit", [])
    if artist_credits and isinstance(artist_credits[0], dict):
        ac_artist = artist_credits[0].get("artist", {})
        canonical_artist = ac_artist.get("name", artist)

    # Collect ISRCs
    isrcs = best_rec.get("isrcs", [])

    logger.debug(
        "MusicBrainz: '%s' → title=%r artist=%r isrcs=%r (sim=%.2f)",
        title, canonical_title, canonical_artist, isrcs, best_sim,
    )
    return canonical_title, canonical_artist, isrcs


# ── Audio feature analysis (Level 3) ─────────────────────────────────────────

# Krumhansl-Schmuckler key profiles
_MAJOR_PROFILE = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_MINOR_PROFILE = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _ffmpeg_to_wav(audio_path: str, duration: int = 60) -> str:
    """Decode audio_path to a temp WAV file via ffmpeg. Returns WAV path.

    Caller is responsible for deleting the file.  Raises RuntimeError if ffmpeg
    is not found or returns a non-zero exit code.

    ffmpeg is searched in PATH first, then a set of common macOS/Linux locations
    (the venv PATH may omit /usr/local/bin on macOS).
    """
    import shutil
    import subprocess
    import tempfile

    ffmpeg_bin = shutil.which("ffmpeg") or shutil.which(
        "ffmpeg",
        path="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/opt/local/bin",
    )
    if not ffmpeg_bin:
        raise RuntimeError("ffmpeg not found; install it to enable audio analysis")

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    wav_path = tmp.name
    tmp.close()

    result = subprocess.run(
        [
            ffmpeg_bin, "-y", "-i", audio_path,
            "-ar", "22050", "-ac", "1",
            "-t", str(duration),
            wav_path,
        ],
        capture_output=True,
        timeout=120,
    )
    if result.returncode != 0:
        try:
            import os
            os.unlink(wav_path)
        except OSError:
            pass
        raise RuntimeError(
            f"ffmpeg exited {result.returncode}: "
            f"{result.stderr.decode(errors='replace')[:300]}"
        )
    return wav_path


def _load_audio_samples(audio_path: str, duration: int = 60):
    """Load audio samples as a numpy float32 array at 22050 Hz mono.

    Strategy:
    1. Try soundfile directly (fast, works for WAV/FLAC/OGG).
    2. Fall back to ffmpeg → WAV → soundfile (handles MP3 and other formats).

    Returns (y: np.ndarray, sr: int).  Raises on total failure.
    """
    import numpy as np
    import soundfile as sf

    # Fast path: soundfile handles WAV/FLAC/OGG without codecs
    try:
        data, sr = sf.read(audio_path, dtype="float32", always_2d=False)
        if data.ndim > 1:
            data = data.mean(axis=1)
        # Trim to requested duration
        max_samples = int(duration * sr)
        if len(data) > max_samples:
            data = data[:max_samples]
        return data, sr
    except Exception:
        pass  # fall through to ffmpeg

    # ffmpeg fallback
    import os
    wav_path = _ffmpeg_to_wav(audio_path, duration=duration)
    try:
        data, sr = sf.read(wav_path, dtype="float32", always_2d=False)
        if data.ndim > 1:
            data = data.mean(axis=1)
        return data, sr
    finally:
        try:
            os.unlink(wav_path)
        except OSError:
            pass


def _estimate_bpm(y, sr: int) -> float:
    """Estimate tempo in BPM from audio samples using scipy — no numba required.

    Algorithm:
    1. Frame the signal and compute RMS onset envelope.
    2. Autocorrelate the envelope.
    3. Find peaks in the tempo range 60–220 BPM and return the highest.
    """
    import numpy as np
    from scipy.signal import find_peaks

    # Frame signal: 512 samples hop, 2048 frame
    hop = 512
    frame_len = 2048
    n_frames = max(1, (len(y) - frame_len) // hop)
    rms = np.array([
        np.sqrt(np.mean(y[i * hop: i * hop + frame_len] ** 2))
        for i in range(n_frames)
    ], dtype=np.float32)

    # Simple onset envelope: half-wave rectified difference
    onset_env = np.maximum(0, np.diff(rms, prepend=rms[0]))
    onset_env -= onset_env.mean()

    # Autocorrelation
    acf = np.correlate(onset_env, onset_env, mode="full")
    acf = acf[len(acf) // 2:]   # keep non-negative lags

    # Convert BPM range to lag samples (fps = sr / hop)
    fps = sr / hop
    lag_min = int(fps * 60 / 220)   # 220 BPM
    lag_max = int(fps * 60 / 60)    # 60 BPM
    lag_min = max(1, lag_min)
    lag_max = min(len(acf) - 1, lag_max)

    if lag_max <= lag_min:
        return 120.0   # fallback

    acf_region = acf[lag_min:lag_max + 1]
    peaks, _ = find_peaks(acf_region, height=0)
    if len(peaks) == 0:
        # No clear peak — return the lag with maximum autocorrelation
        best_lag = lag_min + int(np.argmax(acf_region))
    else:
        best_lag = lag_min + peaks[int(np.argmax(acf_region[peaks]))]

    tempo = fps * 60.0 / best_lag
    # Octave correction: keep in 80–180 BPM range
    while tempo < 80:
        tempo *= 2
    while tempo > 180:
        tempo /= 2
    return round(float(tempo), 1)


def _chroma_stft(y, sr: int, n_fft: int = 4096, hop: int = 2048) -> "np.ndarray":
    """Compute a 12-bin chromagram from audio samples without librosa.

    Uses a manual STFT (numpy rfft) and maps frequency bins to chroma classes
    by the standard A4=440 Hz piano formula.

    Returns an (12, n_frames) array.
    """
    import numpy as np

    # Build STFT frames
    n_frames = max(1, (len(y) - n_fft) // hop + 1)
    window = np.hanning(n_fft)
    chroma = np.zeros((12, n_frames), dtype=np.float32)

    # Frequency bin → chroma mapping (log2 relative to A4=440 Hz)
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sr)  # shape (n_fft//2 + 1,)
    with np.errstate(divide="ignore", invalid="ignore"):
        # semitone class = round(12 * log2(f / 440)) % 12
        # Shift by 9 semitones so bin 0 = C (C is 9 semitones below A4 in octave 4)
        log_bins = 12.0 * np.log2(np.where(freqs > 0, freqs / 440.0, 1e-9))
        chroma_bins = (np.round(log_bins).astype(int) + 9) % 12  # +9: A→C offset

    for i in range(n_frames):
        frame = y[i * hop: i * hop + n_fft]
        if len(frame) < n_fft:
            frame = np.pad(frame, (0, n_fft - len(frame)))
        spectrum = np.abs(np.fft.rfft(frame * window)) ** 2
        np.add.at(chroma[:, i], chroma_bins, spectrum)

    return chroma


def analyze_audio_features(audio_path: str) -> dict:
    """Extract BPM, key, mode and energy from first 60 seconds.

    Pure numpy/scipy/soundfile implementation — no numba, no llvmlite.
    Works on any platform regardless of whether librosa.beat can be imported.

    Returns dict with keys: tempo, key, mode, energy.
    Returns empty dict on failure.
    """
    try:
        import numpy as np
        import soundfile  # noqa — verify it is installed

        y, sr = _load_audio_samples(audio_path, duration=60)

        # BPM via scipy autocorrelation (no numba)
        tempo = _estimate_bpm(y, sr)

        # Key/mode via manual STFT chroma + Krumhansl profiles
        chroma = _chroma_stft(y, sr)
        chroma_mean = chroma.mean(axis=1)
        # Normalise so profile correlation isn't dominated by level
        if chroma_mean.max() > 0:
            chroma_mean = chroma_mean / chroma_mean.max()

        best_major_r, best_major_key = -1.0, 0
        best_minor_r, best_minor_key = -1.0, 0
        for i in range(12):
            rotated = np.roll(chroma_mean, -i)
            r_major = float(np.corrcoef(rotated, _MAJOR_PROFILE)[0, 1])
            r_minor = float(np.corrcoef(rotated, _MINOR_PROFILE)[0, 1])
            if r_major > best_major_r:
                best_major_r, best_major_key = r_major, i
            if r_minor > best_minor_r:
                best_minor_r, best_minor_key = r_minor, i

        if best_major_r >= best_minor_r:
            key_name = _NOTE_NAMES[best_major_key]
            mode = "major"
        else:
            key_name = _NOTE_NAMES[best_minor_key]
            mode = "minor"

        # RMS energy
        rms = float(np.sqrt(np.mean(y ** 2)))

        return {"tempo": round(tempo, 1), "key": key_name, "mode": mode, "energy": round(rms, 4)}

    except Exception as exc:
        logger.debug("Audio analysis failed: %s", exc)
        return {}


def bpm_match_boost(score: float, source_features: dict, cand_features: dict) -> float:
    """Adjust score based on BPM similarity.

    +0.05 if BPM within 2% (or doubles/halves — halving for DJ transitions).
    -0.10 if BPM differs by more than 15%.
    """
    src_bpm = source_features.get("tempo")
    cnd_bpm = cand_features.get("tempo")
    if not src_bpm or not cnd_bpm:
        return score

    # Allow for half/double BPM (common in electronic music)
    ratios = [cnd_bpm / src_bpm, (cnd_bpm * 2) / src_bpm, cnd_bpm / (src_bpm * 2)]
    closest = min(abs(r - 1.0) for r in ratios)

    if closest <= 0.02:
        return min(1.0, score + 0.05)
    elif closest > 0.15:
        return max(0.0, score - 0.10)
    return score


# ── Main public API ───────────────────────────────────────────────────────────

THRESHOLD_MATCHED = 0.90
THRESHOLD_UNCERTAIN = 0.55

# Bump this integer whenever the matching algorithm gains new capabilities.
# Any AudioFingerprint stored with algo_version < MATCH_ALGO_VERSION is
# considered stale and will be re-analyzed the next time it is requested.
#
# v1 → v2: token_set_ratio for artist scoring; "topic" added to VEVO_RE.
#           Handles "AURORA - Topic" auto-generated YouTube channels and
#           real-name vs stage-name mismatches (e.g. "Aurora Aksnes" ↔ "AURORA").
MATCH_ALGO_VERSION = 2


def find_youtube_match(source_title: str, source_artist: str,
                       source_duration_ms: int | None,
                       source_isrc: str | None = None,
                       use_musicbrainz: bool = True,
                       exclude_ids: list | None = None):
    """Find the best YouTube match for a track.

    Level 1: Multiple query formulations, ytsearch n=10, deduplicated candidates.
    Level 2: If best score < THRESHOLD_MATCHED, enrich via MusicBrainz and retry.

    exclude_ids: list of video IDs to skip (previously rejected by the user).

    Returns:
        (video_id, matched_title, confidence, alternatives)
        alternatives — list of {video_id, title, artist, confidence} dicts sorted
                       by confidence desc, above ~60 % of THRESHOLD_UNCERTAIN.
        Returns (None, None, 0.0, []) when no match meets THRESHOLD_UNCERTAIN.
    """
    exclude = set(exclude_ids or [])

    queries = _build_queries(source_title, source_artist)
    candidates = _collect_candidates(queries, n_per_query=15)
    candidates = [c for c in candidates if c.get("video_id") not in exclude]

    best, best_score = _best_from_candidates(
        candidates, source_title, source_artist, source_duration_ms, source_isrc
    )

    logger.debug(
        "Level 1: best_score=%.3f for '%s' by '%s'",
        best_score, source_title, source_artist,
    )

    # Level 2: MusicBrainz enrichment when score is below threshold
    mb_new_candidates: list = []
    effective_isrc = source_isrc
    title_for_alts = source_title
    artist_for_alts = source_artist

    if use_musicbrainz and best_score < THRESHOLD_MATCHED:
        can_title, can_artist, mb_isrcs = _mb_lookup(source_title, source_artist)

        if can_title or mb_isrcs:
            effective_isrc = source_isrc or (mb_isrcs[0] if mb_isrcs else None)
            title_for_alts = can_title or source_title
            artist_for_alts = can_artist or source_artist

            # Re-score existing candidates with enriched metadata
            for cand in candidates:
                score = score_candidate(
                    title_for_alts, artist_for_alts, source_duration_ms,
                    cand["title"], cand["artist"], cand["duration_sec"],
                    source_isrc=effective_isrc,
                )
                if score > best_score:
                    best_score = score
                    best = cand

            # Run fresh searches with canonical metadata if still below threshold
            if best_score < THRESHOLD_MATCHED and (can_title or can_artist):
                mb_queries = _build_queries(title_for_alts, artist_for_alts)
                mb_new_candidates = _collect_candidates(mb_queries, n_per_query=15)
                existing_ids = {c["video_id"] for c in candidates} | exclude

                for cand in mb_new_candidates:
                    if cand["video_id"] in existing_ids:
                        continue
                    score = score_candidate(
                        title_for_alts, artist_for_alts, source_duration_ms,
                        cand["title"], cand["artist"], cand["duration_sec"],
                        source_isrc=effective_isrc,
                    )
                    if score > best_score:
                        best_score = score
                        best = cand

            logger.debug(
                "Level 2 (MusicBrainz): best_score=%.3f, canonical='%s' / '%s'",
                best_score, can_title, can_artist,
            )

    # Deduplicated full candidate pool from both L1 and L2 searches
    existing_l1_ids = {c["video_id"] for c in candidates}
    extra = [c for c in mb_new_candidates
             if c.get("video_id") not in existing_l1_ids and c.get("video_id") not in exclude]
    all_candidates = candidates + extra

    if best and best_score >= THRESHOLD_UNCERTAIN:
        # Build alternatives: ranked pool minus the winner, min score ~60% of threshold
        alt_pool = [c for c in all_candidates if c.get("video_id") != best["video_id"]]
        alternatives = _rank_all_candidates(
            alt_pool, title_for_alts, artist_for_alts, source_duration_ms,
            source_isrc=effective_isrc,
            min_score=THRESHOLD_UNCERTAIN * 0.6,
        )[:5]
        return best["video_id"], best["title"], round(best_score, 4), alternatives

    # No confident match — return top candidates as search results so the user
    # can manually pick one (displayed as a picker in the "Not Found" row).
    # Also run a search with the raw "title artist" query (same as the platform
    # search link) so the displayed results align with what the user sees on YouTube.
    raw_query = f"{source_title} {source_artist}".strip() if source_artist else source_title
    existing_ids = {c.get("video_id") for c in all_candidates} | exclude
    raw_extra = [
        c for c in _collect_candidates([raw_query], n_per_query=10)
        if c.get("video_id") and c["video_id"] not in existing_ids
    ]
    all_candidates = all_candidates + raw_extra

    search_results = _rank_all_candidates(
        all_candidates, title_for_alts, artist_for_alts, source_duration_ms,
        source_isrc=effective_isrc,
        min_score=0.0,
    )[:5]
    return None, None, 0.0, search_results


def classify_confidence(confidence: float) -> str:
    """Map a confidence score to a SyncTrack status string."""
    from api.models import SyncTrack

    if confidence >= THRESHOLD_MATCHED:
        return SyncTrack.Status.MATCHED
    elif confidence >= THRESHOLD_UNCERTAIN:
        return SyncTrack.Status.UNCERTAIN
    else:
        return SyncTrack.Status.NOT_FOUND
