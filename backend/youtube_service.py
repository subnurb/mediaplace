"""YouTube Data API v3 helpers for browsing playlists and tracks.

Uses the stored Google OAuth credentials from a SourceConnection.
The credentials must include the youtube.readonly scope (already requested
during YouTube OAuth alongside youtube.upload).
"""

import re

from googleapiclient.discovery import build


def _build_youtube(source):
    """Build a YouTube API client from a SourceConnection's stored credentials."""
    credentials = source.get_credentials()
    if credentials is None:
        raise ValueError("YouTube credentials expired. Please reconnect your account.")
    return build("youtube", "v3", credentials=credentials)


def _parse_iso_duration(iso: str) -> int | None:
    """Parse ISO 8601 duration (e.g. PT4M33S) to milliseconds."""
    if not iso:
        return None
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if not m:
        return None
    h = int(m.group(1) or 0)
    mn = int(m.group(2) or 0)
    s = int(m.group(3) or 0)
    return (h * 3600 + mn * 60 + s) * 1000


def _best_thumbnail(thumbnails: dict) -> str:
    for key in ("maxres", "standard", "high", "medium", "default"):
        if key in thumbnails:
            return thumbnails[key].get("url", "")
    return ""


# ── Playlists ─────────────────────────────────────────────────────────────────

def get_playlists(source) -> list:
    """Return the user's YouTube playlists plus a virtual 'Liked Videos' entry."""
    youtube = _build_youtube(source)

    playlists = []
    page_token = None

    while True:
        params = {"part": "snippet,contentDetails", "mine": True, "maxResults": 50}
        if page_token:
            params["pageToken"] = page_token

        resp = youtube.playlists().list(**params).execute()

        for item in resp.get("items", []):
            playlists.append({
                "id": item["id"],
                "name": item["snippet"]["title"],
                "track_count": item["contentDetails"].get("itemCount", 0),
                "type": "playlist",
            })

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    # Prepend the special "Liked Videos" playlist (YouTube internal ID: "LL")
    playlists.insert(0, {
        "id": "LL",
        "name": "Liked Videos",
        "track_count": None,
        "type": "likes",
    })

    return playlists


# ── Tracks ────────────────────────────────────────────────────────────────────

def get_playlist_tracks(source, playlist_id: str) -> list:
    """Return normalized tracks for a YouTube playlist (including Liked Videos)."""
    youtube = _build_youtube(source)

    # 1. Collect all playlist items (paginated)
    items = []
    page_token = None

    while True:
        params = {
            "part": "snippet,contentDetails",
            "playlistId": playlist_id,
            "maxResults": 50,
        }
        if page_token:
            params["pageToken"] = page_token

        resp = youtube.playlistItems().list(**params).execute()
        items.extend(resp.get("items", []))

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    if not items:
        return []

    # 2. Batch-fetch video durations (videos.list — 50 IDs per request)
    video_ids = [
        item["contentDetails"]["videoId"]
        for item in items
        if item.get("contentDetails", {}).get("videoId")
    ]

    duration_map = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        vresp = youtube.videos().list(
            part="contentDetails",
            id=",".join(batch),
            maxResults=50,
        ).execute()
        for v in vresp.get("items", []):
            duration_map[v["id"]] = _parse_iso_duration(
                v.get("contentDetails", {}).get("duration", "")
            )

    # 3. Normalize
    tracks = []
    for position, item in enumerate(items):
        snippet = item.get("snippet", {})
        video_id = item.get("contentDetails", {}).get("videoId", "")

        # Skip deleted / private / missing videos
        title = snippet.get("title", "")
        if not video_id or title in ("Deleted video", "Private video"):
            continue

        tracks.append({
            "id": video_id,
            "title": title,
            "artist": snippet.get("videoOwnerChannelTitle", ""),
            "duration_ms": duration_map.get(video_id),
            "artwork_url": _best_thumbnail(snippet.get("thumbnails", {})),
            "permalink_url": f"https://www.youtube.com/watch?v={video_id}",
            "isrc": None,
            "position": position,
        })

    return tracks


# ── Playlist management (write) ───────────────────────────────────────────────

def create_playlist(source, title: str, description: str = "") -> dict:
    """Create a new YouTube playlist. Returns {id, name}."""
    youtube = _build_youtube(source)
    try:
        resp = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {"title": title, "description": description},
                "status": {"privacyStatus": "public"},
            },
        ).execute()
        return {"id": resp["id"], "name": resp["snippet"]["title"]}
    except Exception as e:
        raise ValueError(
            "Failed to create YouTube playlist. Reconnect your YouTube account to grant "
            "playlist management permissions."
        ) from e


def get_playlist_video_ids(source, playlist_id: str) -> set:
    """Return the set of video IDs currently in a playlist (for duplicate detection).

    Returns an empty set if the playlist is not found or not accessible — this lets
    _run_push continue rather than aborting (all tracks will be added, with YouTube
    de-duplicating on its end if needed).
    """
    from googleapiclient.errors import HttpError
    youtube = _build_youtube(source)
    ids = set()
    page_token = None

    while True:
        params = {
            "part": "contentDetails",
            "playlistId": playlist_id,
            "maxResults": 50,
        }
        if page_token:
            params["pageToken"] = page_token

        try:
            resp = youtube.playlistItems().list(**params).execute()
        except HttpError as e:
            if e.resp.status == 404:
                # Playlist not found or not accessible — treat as empty
                return set()
            raise

        for item in resp.get("items", []):
            vid = item.get("contentDetails", {}).get("videoId", "")
            if vid:
                ids.add(vid)

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    return ids


def add_video_to_playlist(source, playlist_id: str, video_id: str) -> bool:
    """Add a video to a YouTube playlist. Returns True on success, False on soft errors."""
    youtube = _build_youtube(source)
    try:
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                }
            },
        ).execute()
        return True
    except Exception as e:
        err = str(e)
        # Forbidden / insufficientPermissions → re-raise with clear message
        if "forbidden" in err.lower() or "insufficientPermissions" in err or "403" in err:
            raise ValueError(
                "Insufficient YouTube permissions to add videos to playlists. "
                "Reconnect your YouTube account."
            ) from e
        return False
