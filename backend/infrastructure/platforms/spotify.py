"""Facade for Spotify platform infrastructure.

Re-exports public API from root-level spotify_service.py.
Import from here for DDD-aligned code:
    from infrastructure.platforms.spotify import get_playlists, get_playlist_tracks
"""

from spotify_service import (  # noqa: F401
    get_playlists,
    get_playlist_tracks,
    find_spotify_match,
    create_playlist,
    get_playlist_track_ids,
    add_tracks_to_playlist,
    remove_tracks_from_playlist,
)
