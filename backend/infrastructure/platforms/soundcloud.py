"""Facade for SoundCloud platform infrastructure.

Re-exports public API from root-level soundcloud_service.py.
Import from here for DDD-aligned code:
    from infrastructure.platforms.soundcloud import get_playlists, get_playlist_tracks
"""

from soundcloud_service import (  # noqa: F401
    get_playlists,
    get_playlist_tracks,
    find_soundcloud_match,
    resolve_track_id,
    create_playlist,
    get_playlist_track_ids,
    add_tracks_to_playlist,
    remove_tracks_from_playlist,
)
