"""Spotify Web API helpers for browsing playlists and tracks.

Uses Spotipy with a custom auth manager that reads tokens from SourceConnection.
Same public API and normalized track/playlist shapes as before for sync and library.
"""

import spotipy

from spotify_auth_manager import SourceConnectionAuthManager


def _sp(source):
    """Return a Spotipy client authenticated with the given SourceConnection."""
    return spotipy.Spotify(auth_manager=SourceConnectionAuthManager(source))


# ── Track normalization ────────────────────────────────────────────────────────

def _normalize_track(item: dict, position: int = 0) -> dict:
    """Convert a Spotify track object (or playlist item) to unified representation."""
    t = item.get("track", item)
    images   = (t.get("album") or {}).get("images") or []
    artwork  = images[0]["url"] if images else ""
    artists  = t.get("artists") or []
    artist   = artists[0].get("name", "") if artists else ""
    isrc     = ((t.get("external_ids") or {}).get("isrc") or None)
    track_id = t.get("id", "")
    return {
        "id":            track_id,
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
    sp = _sp(source)
    data  = sp.current_user_playlists(limit=50)
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

    try:
        liked = sp.current_user_saved_tracks(limit=1)
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

    sp = _sp(source)
    tracks = []
    offset = 0
    limit  = 100

    while True:
        data = sp.playlist_items(
            playlist_id,
            limit=limit,
            offset=offset,
            additional_types=("track",),
        )
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
    sp = _sp(source)
    tracks = []
    offset = 0

    while len(tracks) < limit:
        page_size = min(50, limit - len(tracks))
        data = sp.current_user_saved_tracks(limit=page_size, offset=offset)
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
    sp         = _sp(source)

    for query in queries:
        try:
            data    = sp.search(q=query, type="track", limit=10)
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

    raw_query = f"{title} {artist}".strip() if artist else title
    try:
        raw_data    = sp.search(q=raw_query, type="track", limit=10)
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
    sp              = _sp(source)
    data = sp.user_playlist_create(spotify_user_id, title, public=True)
    return {"id": data["id"], "name": data.get("name", title)}


def get_playlist_track_ids(source, playlist_id: str) -> set:
    """Return the set of bare Spotify track IDs currently in a playlist."""
    sp   = _sp(source)
    ids  = set()
    offset = 0
    limit  = 100

    while True:
        data = sp.playlist_items(
            playlist_id,
            limit=limit,
            offset=offset,
            fields="items(track(id)),next",
            additional_types=("track",),
        )
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

    Deduplicates against existing tracks; batches in chunks of 100.
    Returns True on success.
    """
    try:
        existing = get_playlist_track_ids(source, playlist_id)
        new_ids  = [tid for tid in track_ids if tid not in existing]
        if not new_ids:
            return True
        sp = _sp(source)
        for i in range(0, len(new_ids), 100):
            batch = new_ids[i:i + 100]
            uris  = [f"spotify:track:{tid}" for tid in batch]
            sp.playlist_add_items(playlist_id, uris)
        return True
    except Exception:
        return False


def remove_tracks_from_playlist(source, playlist_id: str, track_ids: list) -> bool:
    """Remove track_ids (bare Spotify IDs) from a Spotify playlist.

    Batches in chunks of 100. Returns True on success.
    """
    try:
        sp = _sp(source)
        for i in range(0, len(track_ids), 100):
            batch = track_ids[i:i + 100]
            uris = [f"spotify:track:{tid}" for tid in batch]
            sp.playlist_remove_all_occurrences_of_items(playlist_id, uris)
        return True
    except Exception:
        return False
