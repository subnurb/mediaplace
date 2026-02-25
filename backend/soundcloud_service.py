"""SoundCloud API helpers for browsing playlists and tracks.

Uses the stored OAuth access token from a SourceConnection.
All requests go to api.soundcloud.com v1 (documented) with
Authorization: OAuth {token} header.
"""

import requests as http
from requests.exceptions import HTTPError

from soundcloud_auth import get_access_token, refresh_access_token

_BASE = "https://api.soundcloud.com"
_TIMEOUT = 15


def _headers(source):
    token = get_access_token(source)
    if not token:
        raise ValueError("SoundCloud source has no valid access token.")
    return {"Authorization": f"OAuth {token}"}


def _get(source, path, params=None):
    """GET with automatic token-refresh retry on 401."""
    try:
        resp = http.get(f"{_BASE}{path}", headers=_headers(source),
                        params=params or {}, timeout=_TIMEOUT)
        if resp.status_code == 401:
            # Token may have expired — try refreshing once
            new_token = refresh_access_token(source)
            if not new_token:
                raise ValueError(
                    "SoundCloud token expired. Please reconnect your SoundCloud account."
                )
            resp = http.get(f"{_BASE}{path}",
                            headers={"Authorization": f"OAuth {new_token}"},
                            params=params or {}, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            raise ValueError(
                "SoundCloud token expired. Please reconnect your SoundCloud account."
            ) from e
        raise


# ── Playlists ─────────────────────────────────────────────────────────────────

def get_playlists(source) -> list:
    """Return a list of the user's playlists/sets including a virtual 'Liked Tracks' entry."""
    data = _get(source, "/me/playlists", {"limit": 50, "linked_partitioning": 1})

    # SoundCloud returns either a list or a paginated object
    items = data if isinstance(data, list) else data.get("collection", [])

    playlists = [
        {
            "id": str(p["id"]),
            "name": p.get("title", "Untitled Playlist"),
            "track_count": p.get("track_count", 0),
            "type": "playlist",
        }
        for p in items
    ]

    # Prepend a virtual "Liked Tracks" entry backed by /me/likes/tracks
    try:
        liked = _get(source, "/me/likes/tracks", {"limit": 1})
        liked_list = liked if isinstance(liked, list) else liked.get("collection", [])
        # Count is not always available; just use a placeholder
        playlists.insert(0, {
            "id": "likes",
            "name": "Liked Tracks",
            "track_count": len(liked_list),  # may be capped at 1
            "type": "likes",
        })
    except Exception:
        pass

    return playlists


# ── Tracks ────────────────────────────────────────────────────────────────────

def _extract_artist(track: dict) -> str:
    """Extract artist for CANDIDATE tracks shown in the not-found picker.

    Prefers publisher_metadata.artist (set by labels/distributors).
    Falls back to user.username (stable URL handle) to avoid showing
    curator display names like 'Marée Basse' for tracks they didn't make.
    """
    pub = track.get("publisher_metadata") or {}
    if pub.get("artist"):
        return pub["artist"]

    user = track.get("user") or {}
    return user.get("username") or ""


def _extract_source_artist(track: dict) -> str:
    """Extract artist for SOURCE tracks being matched to another platform.

    Prefers publisher_metadata.artist, then user.full_name (the account's
    display name). For self-uploaded tracks the display name IS the artist
    (e.g. 'AD†AM', 'BCCO'), making it far more useful for YouTube search
    queries and scoring than the username slug ('adam0000000000001').
    """
    pub = track.get("publisher_metadata") or {}
    if pub.get("artist"):
        return pub["artist"]

    user = track.get("user") or {}
    return user.get("full_name") or user.get("username") or ""


def _normalize_track(t: dict, position: int = 0) -> dict:
    """Convert a raw SoundCloud track dict to a unified representation."""
    # Prefer artwork at 500×500 resolution; fall back to the default "large" (100×100)
    artwork = (t.get("artwork_url") or "").replace("-large", "-t500x500")

    return {
        "id": str(t["id"]),
        "title": t.get("title", ""),
        "artist": _extract_source_artist(t),
        "duration_ms": t.get("duration"),          # milliseconds
        "artwork_url": artwork,
        "permalink_url": t.get("permalink_url", ""),
        "isrc": t.get("isrc") or None,
        "position": position,
    }


def get_playlist_tracks(source, playlist_id: str) -> list:
    """Return normalized tracks for a playlist or liked tracks."""
    if playlist_id == "likes":
        return _get_liked_tracks(source)

    data = _get(source, f"/playlists/{playlist_id}", {"limit": 200})
    raw_tracks = data.get("tracks", [])
    return [_normalize_track(t, i) for i, t in enumerate(raw_tracks) if t]


def _get_liked_tracks(source, limit: int = 200) -> list:
    """Fetch the user's liked tracks (all pages up to limit)."""
    tracks = []
    url = f"{_BASE}/me/likes/tracks"
    # Resolve headers once; the first _get() call will have already refreshed if needed
    headers = _headers(source)

    while url and len(tracks) < limit:
        resp = http.get(url, headers=headers,
                        params={"limit": min(50, limit - len(tracks))},
                        timeout=_TIMEOUT)
        if resp.status_code == 401:
            new_token = refresh_access_token(source)
            if not new_token:
                raise ValueError(
                    "SoundCloud token expired. Please reconnect your SoundCloud account."
                )
            headers = {"Authorization": f"OAuth {new_token}"}
            resp = http.get(url, headers=headers,
                            params={"limit": min(50, limit - len(tracks))},
                            timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        items = data if isinstance(data, list) else data.get("collection", [])
        for item in items:
            # /me/likes/tracks wraps the track inside a "track" key sometimes
            track = item.get("track", item)
            if track and track.get("id"):
                tracks.append(_normalize_track(track, len(tracks)))

        # Follow next_href for pagination
        next_href = data.get("next_href") if isinstance(data, dict) else None
        url = next_href if next_href else None

    return tracks


# ── Track search (for matching) ───────────────────────────────────────────────

def find_soundcloud_match(source, title: str, artist: str,
                          duration_ms: int | None,
                          isrc: str | None = None,
                          exclude_ids: list | None = None):
    """Search SoundCloud for the best match for a track.

    Runs multiple queries (artist+cleaned title, title-only) and deduplicates
    results before scoring, preferring full_name over username for artist.

    exclude_ids: list of permalink URLs previously rejected by the user.

    Returns (permalink_url, matched_title, confidence, alternatives).
    alternatives — list of {video_id: permalink_url, title, artist, confidence}.
    Returns (None, None, 0.0, []) when no match meets THRESHOLD_UNCERTAIN.
    """
    from music_matcher import score_candidate, THRESHOLD_UNCERTAIN, _build_queries

    exclude = set(exclude_ids or [])
    queries = _build_queries(title, artist)

    seen_ids = set()
    candidates = []
    for query in queries:
        try:
            data = _get(source, "/tracks", {"q": query, "limit": 10})
        except Exception:
            continue
        results = data if isinstance(data, list) else data.get("collection", [])
        for track in results:
            if not track or not track.get("id") or not track.get("title"):
                continue
            permalink = track.get("permalink_url", "")
            if track["id"] not in seen_ids and permalink not in exclude:
                seen_ids.add(track["id"])
                candidates.append(track)

    best_score = 0.0
    best = None

    for track in candidates:
        cand_artist = _extract_artist(track)
        cand_duration_sec = (track.get("duration") or 0) / 1000

        score = score_candidate(
            title, artist, duration_ms,
            track["title"], cand_artist, cand_duration_sec,
            source_isrc=isrc,
        )

        if score > best_score:
            best_score = score
            best = track

    def _sc_score(track):
        cand_artist = _extract_artist(track)
        cand_duration_sec = (track.get("duration") or 0) / 1000
        return score_candidate(
            title, artist, duration_ms,
            track["title"], cand_artist, cand_duration_sec,
            source_isrc=isrc,
        ), cand_artist

    if best and best_score >= THRESHOLD_UNCERTAIN:
        winner_permalink = best.get("permalink_url", "")
        alternatives = []
        for track in candidates:
            if track is best:
                continue
            conf, cand_artist = _sc_score(track)
            if conf >= THRESHOLD_UNCERTAIN * 0.6:
                alternatives.append({
                    "video_id": track.get("permalink_url", ""),
                    "title": track["title"],
                    "artist": cand_artist,
                    "confidence": round(conf, 4),
                })
        alternatives.sort(key=lambda x: x["confidence"], reverse=True)
        return winner_permalink, best["title"], round(best_score, 4), alternatives[:5]

    # No confident match — return top candidates as search results for manual selection.
    # Also run a search with the raw "title artist" query (same as the platform search
    # link) so the displayed results align with what the user sees on SoundCloud.
    raw_query = f"{title} {artist}".strip() if artist else title
    existing_ids = {t.get("id") for t in candidates if t.get("id")}
    try:
        raw_data = _get(source, "/tracks", {"q": raw_query, "limit": 10})
        raw_results = raw_data if isinstance(raw_data, list) else raw_data.get("collection", [])
        for track in raw_results:
            if track and track.get("id") and track.get("title") and track["id"] not in existing_ids:
                existing_ids.add(track["id"])
                candidates.append(track)
    except Exception:
        pass

    search_results = []
    for track in candidates:
        conf, cand_artist = _sc_score(track)
        search_results.append({
            "video_id": track.get("permalink_url", ""),
            "title": track["title"],
            "artist": cand_artist,
            "confidence": round(conf, 4),
        })
    search_results.sort(key=lambda x: x["confidence"], reverse=True)
    return None, None, 0.0, search_results[:5]


# ── Playlist management (write) ───────────────────────────────────────────────

def resolve_track_id(source, permalink_url: str) -> str | None:
    """Resolve a SoundCloud permalink URL to its numeric track ID.

    Used during playlist push to convert stored permalink URLs (which are used
    for display and audio download) into the numeric IDs required by the API.
    Returns None if the URL cannot be resolved.
    """
    try:
        data = _get(source, "/resolve", {"url": permalink_url})
        return str(data["id"]) if data.get("id") else None
    except Exception:
        return None


def create_playlist(source, title: str) -> dict:
    """Create a new SoundCloud playlist. Returns {id, name}."""
    resp = http.post(
        f"{_BASE}/playlists",
        headers=_headers(source),
        json={"playlist": {"title": title, "sharing": "public"}},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return {"id": str(data["id"]), "name": data.get("title", title)}


def get_playlist_track_ids(source, playlist_id: str) -> set:
    """Return the set of track IDs currently in a SoundCloud playlist."""
    data = _get(source, f"/playlists/{playlist_id}", {"limit": 200})
    return {str(t["id"]) for t in data.get("tracks", []) if t and t.get("id")}


def add_tracks_to_playlist(source, playlist_id: str, track_ids: list) -> bool:
    """Append track_ids to a SoundCloud playlist.

    SoundCloud requires replacing the full track list via PUT. We fetch the
    current tracks first, then append the new ones (deduplicating on the way).
    Returns True on success.
    """
    try:
        existing_data = _get(source, f"/playlists/{playlist_id}", {"limit": 200})
        current_ids = [str(t["id"]) for t in existing_data.get("tracks", []) if t and t.get("id")]
        existing_set = set(current_ids)
        new_ids = [tid for tid in track_ids if tid not in existing_set]
        if not new_ids:
            return True  # all already present

        updated = current_ids + new_ids
        resp = http.put(
            f"{_BASE}/playlists/{playlist_id}",
            headers=_headers(source),
            json={"playlist": {"tracks": [{"id": tid} for tid in updated]}},
            timeout=_TIMEOUT,
        )
        return resp.status_code in (200, 204)
    except Exception:
        return False
