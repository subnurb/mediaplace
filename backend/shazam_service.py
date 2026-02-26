"""ShazamIO integration — audio recognition via the Shazam API.

Wraps the async ShazamIO library in a synchronous interface for use in
Django views and background threads.

Safety notes
------------
* shazamio-core is a native Rust extension.  If it crashes (segfault) the
  whole process dies — no Python try/except can catch that.  Keep this
  module isolated: never call it from a hot code path during sync.
* We use asyncio.new_event_loop() + run_until_complete() explicitly instead
  of asyncio.run() to avoid "event loop already running" errors when called
  from Django background threads on Python ≤ 3.11.
* Audio is read as bytes (not a path string) for cross-version compatibility
  with shazamio 0.4–0.8+.
* Files larger than MAX_FILE_MB are skipped to avoid OOM in the Rust layer.

Returns None on any failure (no match, timeout, missing library, error).
"""

import logging
import os

logger = logging.getLogger(__name__)

# Skip files larger than this to limit memory usage in the native extension
MAX_FILE_MB = 15


def recognize_audio(audio_path: str, timeout: int = 30) -> dict | None:
    """Identify an audio file using Shazam.

    Returns a dict with keys:
        shazam_id, title, artist, album, genre, spotify_uri, cover_url
    Returns None if not installed, file too large, no match, or any error.
    """
    try:
        from shazamio import Shazam  # noqa: F401
    except ImportError:
        logger.debug("[shazam] shazamio not installed — skipping recognition")
        return None

    # Guard against very large files (risk of OOM in native extension)
    try:
        size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        if size_mb > MAX_FILE_MB:
            logger.debug("[shazam] file too large (%.1f MB > %d MB), skipping %s",
                         size_mb, MAX_FILE_MB, audio_path)
            return None
    except OSError:
        return None

    # Read audio bytes once (more compatible across shazamio versions than passing a path)
    try:
        with open(audio_path, "rb") as fh:
            audio_bytes = fh.read()
    except OSError as exc:
        logger.warning("[shazam] cannot read %s: %s", audio_path, exc)
        return None

    import asyncio

    async def _run():
        shazam = Shazam()
        try:
            return await asyncio.wait_for(shazam.recognize(audio_bytes), timeout=timeout)
        except asyncio.TimeoutError:
            logger.debug("[shazam] timeout recognizing %s", audio_path)
            return None

    loop = None
    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(_run())
    except Exception as exc:
        logger.warning("[shazam] error recognizing %s: %s", audio_path, exc)
        return None
    finally:
        if loop is not None:
            try:
                loop.close()
            except Exception:
                pass

    if not result:
        return None

    track = result.get("track") or {}
    if not track:
        logger.debug("[shazam] no track match for %s", audio_path)
        return None

    # Spotify URI from providers hub
    spotify_uri = ""
    for provider in track.get("hub", {}).get("providers", []):
        if provider.get("type") == "SPOTIFY":
            for opt in provider.get("options", []):
                if opt.get("id") == "trackid":
                    spotify_uri = f"spotify:track:{opt.get('value', '')}"
                    break

    # Best available cover art URL
    images = track.get("images", {})
    cover_url = images.get("coverarthq") or images.get("coverart") or ""

    # Primary genre
    genre = track.get("genres", {}).get("primary", "")

    # Album title (first metadata section tagged "Album")
    album = ""
    for section in track.get("sections", []):
        for item in section.get("metadata", []):
            if item.get("title", "").lower() == "album":
                album = item.get("text", "")
                break
        if album:
            break

    return {
        "shazam_id": str(track.get("key", "")),
        "title": track.get("title", ""),
        "artist": track.get("subtitle", ""),
        "album": album,
        "genre": genre,
        "spotify_uri": spotify_uri,
        "cover_url": cover_url,
    }


if __name__ == "__main__":
    # Called as a subprocess by _schedule_shazam_enrichment so that a
    # shazamio-core segfault only kills this child process, not Django.
    # Usage: python shazam_service.py <audio_path>
    # Outputs JSON result to stdout, nothing on failure.
    import json
    import sys

    # Probe import before doing anything else — exit cleanly if the native
    # extension is broken (e.g. pyo3_log segfault on Python 3.14) rather
    # than letting the crash reporter fire.
    try:
        from shazamio import Shazam as _Shazam  # noqa: F401
    except Exception:
        sys.exit(1)

    if len(sys.argv) < 2:
        sys.exit(1)
    _result = recognize_audio(sys.argv[1])
    if _result:
        print(json.dumps(_result))
