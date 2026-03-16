"""Spotipy auth manager that uses SourceConnection token storage.

Allows spotipy.Spotify(auth_manager=...) to use tokens stored in the DB
per SourceConnection, with refresh when expired. Auth flow (PKCE, callback)
remains in spotify_auth; this only adapts token access for the Spotipy client.
"""

import time

from spotify_auth import get_token_info, refresh_access_token


def _is_token_expired(token_info: dict) -> bool:
    """True if token expires in less than 60 seconds (Spotipy convention)."""
    if not token_info or "expires_at" not in token_info:
        return True
    return token_info["expires_at"] - int(time.time()) < 60


class SourceConnectionAuthManager:
    """Spotipy-compatible auth manager that reads/refreshes token from a SourceConnection."""

    def __init__(self, source):
        """
        Args:
            source: A SourceConnection instance (source_type=SPOTIFY) with credentials_data.
        """
        self._source = source

    def get_access_token(self, as_dict=False, check_cache=True):
        """
        Return a valid access token, refreshing if expired.
        Spotipy calls this with as_dict=False to get the Bearer token string.
        """
        token_info = get_token_info(self._source)
        if not token_info:
            raise ValueError("Spotify source has no valid access token. Please reconnect.")
        if check_cache and _is_token_expired(token_info):
            new_token = refresh_access_token(self._source)
            if new_token:
                if as_dict:
                    token_info = get_token_info(self._source)
                    if token_info:
                        return dict(token_info)
                else:
                    return new_token
        if as_dict:
            return token_info
        return token_info.get("access_token")
