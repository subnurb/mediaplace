"""Spotify Web API helpers for browsing playlists and tracks.

Uses the stored OAuth access token from a SourceConnection.
All requests go to api.spotify.com/v1 with Authorization: Bearer {token} header.
"""

import requests as http
from requests.exceptions import HTTPError

from spotify_auth import get_access_token, refresh_access_token

_BASE    = "https://api.spotify.com/v1"
_TIMEOUT = 15


def _headers(source):
    token = get_access_token(source)
    if not token:
        raise ValueError("Spotify source has no valid access token.")
    return {"Authorization": f"Bearer {token}"}


def _get(source, path, params=None):
    """GET with automatic token-refresh retry on 401."""
    try:
        resp = http.get(f"{_BASE}{path}", headers=_headers(source),
                        params=params or {}, timeout=_TIMEOUT)
        if resp.status_code == 401:
            new_token = refresh_access_token(source)
            if not new_token:
                raise ValueError(
                    "Spotify token expired. Please reconnect your Spotify account."
                )
            resp = http.get(f"{_BASE}{path}",
                            headers={"Authorization": f"Bearer {new_token}"},
                            params=params or {}, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            raise ValueError(
                "Spotify token expired. Please reconnect your Spotify account."
            ) from e
        raise


def _post(source, path, json_body):
    """POST with automatic token-refresh retry on 401."""
    try:
        resp = http.post(f"{_BASE}{path}", headers=_headers(source),
                         json=json_body, timeout=_TIMEOUT)
        if resp.status_code == 401:
            new_token = refresh_access_token(source)
            if not new_token:
                raise ValueError(
                    "Spotify token expired. Please reconnect your Spotify account."
                )
            resp = http.post(f"{_BASE}{path}",
                             headers={"Authorization": f"Bearer {new_token}"},
                             json=json_body, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json() if resp.content else {}
    except HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            raise ValueError(
                "Spotify token expired. Please reconnect your Spotify account."
            ) from e
        raise


# ── Track normalization ────────────────────────────────────────────────────────

def _normalize_track(item: dict, position: int = 0) -> dict:
    """Convert a Spotify track object (or playlist item) to unified representation."""
    # Playlist items wrap the track inside a "track" key
    t = item.get("track", item)
    images   = (t.get("album") or {}).get("images") or []
    artwork  = images[0]["url"] if images else ""
    artists  = t.get("artists") or []
    artist   = artists[0].get("name", "") if artists else ""
    isrc     = ((t.get("external_ids") or {}).get("isrc") or None)
    track_id = t.get("id", "")
    return {
        "id":            track_id,                                         # bare Spotify track ID
        "title":         t.get("name", ""),
        "artist":        artist,
        "duration_ms":   t.get("duration_ms"),
        "artwork_url":   artwork,
        "permalink_url": f"https://open.spotify.com/track/{track_id}",
        "isrc":          isrc,
        "position":      position,
    }


# ── Playlists ──────────────────────────────────────────────────────────────────

def get_playlists(source) -> list:
    """Return a list of the user's playlists including a virtual 'Liked Songs' entry."""
    data  = _get(source, "/me/playlists", {"limit": 50})
    items = data.get("items", [])

    playlists = [
        {
            "id":          p["id"],
            "name":        p.get("name", "Untitled Playlist"),
            "track_count": (p.get("tracks") or {}).get("total", 0),
            "type":        "playlist",
        }
        for p in items if p
    ]

    # Prepend virtual "Liked Songs" entry backed by /me/tracks
    try:
        liked = _get(source, "/me/tracks", {"limit": 1})
        playlists.insert(0, {
            "id":          "liked",
            "name":        "Liked Songs",
            "track_count": liked.get("total", 0),
            "type":        "likes",
        })
    except Exception:
        pass

    return playlists


# ── Tracks ─────────────────────────────────────────────────────────────────────

def get_playlist_tracks(source, playlist_id: str) -> list:
    """Return normalized tracks for a playlist or liked tracks."""
    if playlist_id == "liked":
        return _get_liked_tracks(source)

    tracks  = []
    offset  = 0
    path    = f"/playlists/{playlist_id}/tracks"
    fields  = "items(track(id,name,artists,duration_ms,album(images),external_ids)),next,total"

    while True:
        data  = _get(source, path, {"limit": 100, "offset": offset, "fields": fields})
        items = data.get("items", [])
        for item in items:
            t = (item or {}).get("track")
            if t and t.get("id"):
                tracks.append(_normalize_track(item, len(tracks)))
        if not data.get("next") or not items:
            break
        offset += len(items)

    return tracks


def _get_liked_tracks(source, limit: int = 200) -> list:
    """Fetch the user's liked/saved tracks (all pages up to limit)."""
    tracks = []
    offset = 0

    while len(tracks) < limit:
        data  = _get(source, "/me/tracks", {
            "limit":  min(50, limit - len(tracks)),
            "offset": offset,
        })
        items = data.get("items", [])
        for item in items:
            t = (item or {}).get("track")
            if t and t.get("id"):
                tracks.append(_normalize_track(item, len(tracks)))
        if not data.get("next") or not items:
            break
        offset += len(items)

    return tracks


# ── Track search (for matching) ────────────────────────────────────────────────

def find_spotify_match(source, title: str, artist: str,
                       duration_ms: int | None,
                       isrc: str | None = None,
                       exclude_ids: list | None = None):
    """Search Spotify for the best match for a track.

    Runs multiple queries and deduplicates results before scoring.
    exclude_ids: list of bare Spotify track IDs previously rejected by the user.

    Returns (track_id, matched_title, confidence, alternatives).
    Returns (None, None, 0.0, []) when no match meets THRESHOLD_UNCERTAIN.
    """
    from music_matcher import score_candidate, THRESHOLD_UNCERTAIN, _build_queries

    exclude    = set(exclude_ids or [])
    queries    = _build_queries(title, artist)
    seen       = set()
    candidates = []

    for query in queries:
        try:
            data    = _get(source, "/search", {"q": query, "type": "track", "limit": 10})
            results = (data.get("tracks") or {}).get("items", [])
        except Exception:
            continue
        for t in results:
            if t and t.get("id") and t["id"] not in seen and t["id"] not in exclude:
                seen.add(t["id"])
                candidates.append(t)

    def _score_track(t):
        cand_artist  = ((t.get("artists") or [{}])[0]).get("name", "")
        cand_dur_sec = (t.get("duration_ms") or 0) / 1000
        cand_isrc    = (t.get("external_ids") or {}).get("isrc")
        return score_candidate(
            title, artist, duration_ms,
            t.get("name", ""), cand_artist, cand_dur_sec,
            source_isrc=isrc, cand_isrc=cand_isrc,
        ), cand_artist

    best_score, best = 0.0, None
    for t in candidates:
        s, _ = _score_track(t)
        if s > best_score:
            best_score, best = s, t

    if best and best_score >= THRESHOLD_UNCERTAIN:
        alternatives = []
        for t in candidates:
            if t is best:
                continue
            conf, cand_artist = _score_track(t)
            if conf >= THRESHOLD_UNCERTAIN * 0.6:
                alternatives.append({
                    "video_id":   t["id"],
                    "title":      t.get("name", ""),
                    "artist":     cand_artist,
                    "confidence": round(conf, 4),
                })
        alternatives.sort(key=lambda x: x["confidence"], reverse=True)
        return best["id"], best.get("name", ""), round(best_score, 4), alternatives[:5]

    # No confident match — also try a raw "title artist" query to widen search results
    raw_query = f"{title} {artist}".strip() if artist else title
    try:
        raw_data    = _get(source, "/search", {"q": raw_query, "type": "track", "limit": 10})
        raw_results = (raw_data.get("tracks") or {}).get("items", [])
        for t in raw_results:
            if t and t.get("id") and t["id"] not in seen and t["id"] not in exclude:
                seen.add(t["id"])
                candidates.append(t)
    except Exception:
        pass

    search_results = []
    for t in candidates:
        conf, cand_artist = _score_track(t)
        search_results.append({
            "video_id":   t["id"],
            "title":      t.get("name", ""),
            "artist":     cand_artist,
            "confidence": round(conf, 4),
        })
    search_results.sort(key=lambda x: x["confidence"], reverse=True)
    return None, None, 0.0, search_results[:5]


# ── Playlist management (write) ────────────────────────────────────────────────

def create_playlist(source, title: str) -> dict:
    """Create a new Spotify playlist. Returns {id, name}."""
    config          = source.config or {}
    spotify_user_id = config.get("spotify_user_id", "me")
    data = _post(
        source,
        f"/users/{spotify_user_id}/playlists",
        {"name": title, "public": True},
    )
    return {"id": data["id"], "name": data.get("name", title)}


def get_playlist_track_ids(source, playlist_id: str) -> set:
    """Return the set of bare Spotify track IDs currently in a playlist."""
    ids    = set()
    offset = 0

    while True:
        data  = _get(source, f"/playlists/{playlist_id}/tracks", {
            "fields": "items(track(id)),next",
            "limit":  100,
            "offset": offset,
        })
        items = data.get("items", [])
        for item in items:
            t = (item or {}).get("track")
            if t and t.get("id"):
                ids.add(t["id"])
        if not data.get("next") or not items:
            break
        offset += len(items)

    return ids


def add_tracks_to_playlist(source, playlist_id: str, track_ids: list) -> bool:
    """Append track_ids (bare Spotify IDs) to a Spotify playlist.

    Unlike SoundCloud, Spotify's POST endpoint adds tracks without replacing
    the full list, so we only need to fetch existing IDs to deduplicate.
    Spotify allows max 100 URIs per request — batches automatically.
    Returns True on success.
    """
    try:
        existing = get_playlist_track_ids(source, playlist_id)
        new_ids  = [tid for tid in track_ids if tid not in existing]
        if not new_ids:
            return True
        for i in range(0, len(new_ids), 100):
            batch = new_ids[i:i + 100]
            uris  = [f"spotify:track:{tid}" for tid in batch]
            _post(source, f"/playlists/{playlist_id}/tracks", {"uris": uris})
        return True
    except Exception:
        return False
