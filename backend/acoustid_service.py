"""AcoustID audio fingerprinting and AcousticBrainz feature lookup.

Workflow:
  1. fingerprint_audio(path) — generate a Chromaprint fingerprint locally via fpcalc
  2. lookup_mbid(path)       — fingerprint + query AcoustID API → MBID
  3. get_acousticbrainz_features(mbid) — fetch BPM/key/mode without downloading audio

AcoustID is free for non-commercial use (register at https://acoustid.org/new-application).
Rate limit: 3 req/s. The pyacoustid library handles this internally.

AcousticBrainz is frozen (data collection ended 2022) but still accessible.
Covers ~7.5 million recordings (popular music up to 2022). CC0 licensed.

Dependencies:
    pip install pyacoustid
    brew install chromaprint   # macOS
    apt install libchromaprint-tools  # Ubuntu/Debian
"""

import json
import logging
import ssl
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

_ACOUSTICBRAINZ_BASE = "https://acousticbrainz.org/api/v1"


def _acoustid_api_key() -> str:
    """Return the configured AcoustID API key (lazy import to avoid circular import)."""
    from django.conf import settings
    return getattr(settings, "ACOUSTID_API_KEY", "")


def fingerprint_audio(path: str) -> tuple[str, int] | None:
    """Generate a Chromaprint fingerprint for an audio file using fpcalc.

    Requires the `chromaprint` system library or the `fpcalc` binary on PATH.

    Returns:
        (fingerprint_string, duration_seconds) or None on failure.
    """
    try:
        import acoustid
        duration, fingerprint = acoustid.fingerprint_file(path)
        if fingerprint and duration:
            return fingerprint, int(duration)
        return None
    except Exception as exc:
        logger.debug("Chromaprint fingerprinting failed for %r: %s", path, exc)
        return None


def lookup_mbid(audio_path: str) -> tuple[str | None, float, str]:
    """Fingerprint an audio file, query the AcoustID API, and return the best MBID.

    Returns:
        (mbid, score, chromaprint_str)
        mbid            — MusicBrainz Recording ID, or None if no confident match.
        score           — AcoustID confidence 0–1 (0.0 on failure).
        chromaprint_str — raw Chromaprint fingerprint string (empty string on failure).

    The chromaprint is returned so callers can cache it alongside the MBID without
    needing a second call to fingerprint_audio().
    """
    api_key = _acoustid_api_key()
    if not api_key:
        logger.debug("AcoustID API key not configured; skipping fingerprint lookup")
        return None, 0.0, ""

    fp = fingerprint_audio(audio_path)
    if not fp:
        return None, 0.0, ""

    fingerprint, duration = fp

    try:
        import acoustid

        raw = acoustid.lookup(api_key, fingerprint, duration, meta="recordings")
        results = list(acoustid.parse_lookup_result(raw))
    except Exception as exc:
        logger.debug("AcoustID API lookup failed: %s", exc)
        return None, 0.0, fingerprint

    if not results:
        return None, 0.0, fingerprint

    # Results are (score, recording_id, title, artist) tuples, sorted by score desc
    best = results[0]
    score = best[0]
    mbid = best[1]

    if score >= 0.80 and mbid:
        logger.debug("AcoustID: %r → MBID=%s (score=%.2f)", audio_path, mbid, score)
        return mbid, score, fingerprint

    return None, 0.0, fingerprint


def get_acousticbrainz_features(mbid: str) -> dict:
    """Fetch pre-analyzed BPM, key, and mode from AcousticBrainz by MBID.

    Uses urllib with SSL bypass (same approach as MusicBrainz in music_matcher.py).
    Returns a dict with keys: bpm, key, mode.  Returns {} on failure or missing data.

    Note: AcousticBrainz is frozen (2022); coverage is good for popular releases.
    """
    if not mbid:
        return {}

    url = f"{_ACOUSTICBRAINZ_BASE}/{mbid}/high-level"
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "MediaplaceApp/1.0 (mediaplace@example.com)"}
        )
        with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logger.debug("AcousticBrainz lookup failed for MBID %s: %s", mbid, exc)
        return {}

    # High-level data path: tonal.key_key, tonal.key_scale, rhythm.bpm_histogram_first_peak_bpm
    tonal = data.get("tonal", {})
    rhythm = data.get("rhythm", {})

    key = tonal.get("key_key", {})
    if isinstance(key, dict):
        key = key.get("value", "")
    scale = tonal.get("key_scale", {})
    if isinstance(scale, dict):
        scale = scale.get("value", "")
    bpm_data = rhythm.get("bpm_histogram_first_peak_bpm", {})
    if isinstance(bpm_data, dict):
        bpm = bpm_data.get("value")
    else:
        bpm = bpm_data

    result = {}
    if key:
        result["key"] = str(key)
    if scale:
        result["mode"] = str(scale)
    if bpm:
        try:
            result["bpm"] = float(bpm)
        except (TypeError, ValueError):
            pass

    if result:
        logger.debug("AcousticBrainz: MBID=%s → %s", mbid, result)
    return result


def get_mbid_isrcs(mbid: str) -> list[str]:
    """Fetch ISRCs for a given MBID from MusicBrainz.

    Reuses the same urllib/SSL pattern as music_matcher._mb_lookup.
    Returns a list of ISRC strings (may be empty).
    """
    if not mbid:
        return []

    url = (
        f"https://musicbrainz.org/ws/2/recording/{mbid}"
        f"?inc=isrcs&fmt=json"
    )
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "MediaplaceApp/1.0 (mediaplace@example.com)",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("isrcs", [])
    except Exception as exc:
        logger.debug("MusicBrainz ISRC fetch failed for MBID %s: %s", mbid, exc)
        return []
