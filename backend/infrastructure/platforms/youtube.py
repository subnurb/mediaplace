"""Facade for YouTube platform infrastructure.

Re-exports public API from root-level youtube_service.py.
Import from here for DDD-aligned code:
    from infrastructure.platforms.youtube import get_playlists, get_playlist_tracks
"""

from youtube_service import (  # noqa: F401
    get_playlists,
    get_playlist_tracks,
    create_playlist,
    get_playlist_video_ids,
    add_video_to_playlist,
    remove_video_from_playlist,
)
