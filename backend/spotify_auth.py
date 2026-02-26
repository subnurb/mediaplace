"""Spotify OAuth 2.0 PKCE helpers.

Settings required (config/settings_private.py):
  SPOTIFY_CLIENT_ID
  SPOTIFY_REDIRECT_URI  (optional — defaults to localhost)
  (no client secret needed for PKCE token exchange)

The redirect URI must also be registered in the Spotify Developer Dashboard.
"""

import base64
import hashlib
import json
import os
import urllib.parse

import requests as http


_AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
_TOKEN_URL     = "https://accounts.spotify.com/api/token"
_ME_URL        = "https://api.spotify.com/v1/me"

_SCOPES = " ".join([
    "playlist-read-private",
    "playlist-read-collaborative",
    "playlist-modify-public",
    "playlist-modify-private",
    "user-library-read",
])


def _cfg():
    """Return (client_id, redirect_uri) from Django settings."""
    from django.conf import settings
    return (
        getattr(settings, "SPOTIFY_CLIENT_ID", ""),
        getattr(settings, "SPOTIFY_REDIRECT_URI",
                "http://localhost:8000/api/auth/spotify/callback/"),
    )


def _pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for PKCE S256."""
    verifier  = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
    digest    = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def get_auth_url(user) -> tuple[str, str]:
    """Return (auth_url, state). State encodes user_id + code_verifier.

    The code_verifier is embedded in the state param so it can be recovered at
    callback time without relying on a server-side session store.
    State format: "{user_id}.{code_verifier}"
    """
    client_id, redirect_uri = _cfg()
    if not client_id:
        raise ValueError(
            "Spotify credentials not configured. "
            "Set SPOTIFY_CLIENT_ID in settings_private.py."
        )
    verifier, challenge = _pkce_pair()
    # state serves double duty: CSRF token (unique per request) + verifier carrier
    state = f"{user.id}.{verifier}"
    params = {
        "client_id":             client_id,
        "response_type":         "code",
        "redirect_uri":          redirect_uri,
        "scope":                 _SCOPES,
        "state":                 state,
        "code_challenge_method": "S256",
        "code_challenge":        challenge,
    }
    auth_url = f"{_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"
    return auth_url, state


def exchange_code_for_user(user, code: str, code_verifier: str):
    """Exchange an authorization code + PKCE verifier for tokens.

    Persists the resulting SourceConnection (or updates an existing one for the
    same Spotify user account). Returns ("new"|"updated", display_name).
    """
    from api.models import SourceConnection

    client_id, redirect_uri = _cfg()

    resp = http.post(
        _TOKEN_URL,
        data={
            "grant_type":    "authorization_code",
            "code":          code,
            "redirect_uri":  redirect_uri,
            "client_id":     client_id,
            "code_verifier": code_verifier,
        },
        timeout=15,
    )
    resp.raise_for_status()
    token_data = resp.json()

    me_resp = http.get(
        _ME_URL,
        headers={"Authorization": f"Bearer {token_data['access_token']}"},
        timeout=10,
    )
    me_resp.raise_for_status()
    profile = me_resp.json()

    display_name    = profile.get("display_name") or profile.get("id", "Spotify")
    spotify_user_id = profile.get("id", "")

    credentials_bytes = json.dumps(token_data).encode()

    if spotify_user_id:
        # Deduplicate: same Spotify account → update existing connection
        existing = SourceConnection.objects.filter(
            user=user,
            source_type=SourceConnection.SourceType.SPOTIFY,
            config__spotify_user_id=spotify_user_id,
        ).first()
        if existing:
            existing.credentials_data = credentials_bytes
            existing.name = display_name
            existing.is_active = True
            existing.save(update_fields=["credentials_data", "name", "is_active", "updated_at"])
            return "updated", display_name

    SourceConnection.objects.create(
        user=user,
        source_type=SourceConnection.SourceType.SPOTIFY,
        name=display_name,
        credentials_data=credentials_bytes,
        config={"spotify_user_id": spotify_user_id},
    )
    return "new", display_name


def get_access_token(source) -> str | None:
    """Return the stored access token string, or None."""
    if not source.credentials_data:
        return None
    try:
        return json.loads(bytes(source.credentials_data).decode()).get("access_token")
    except Exception:
        return None


def refresh_access_token(source) -> str | None:
    """Refresh the Spotify access token using the stored refresh_token.

    Updates source.credentials_data in place and saves to DB.
    Returns the new access_token string, or None if refresh is not possible.
    """
    if not source.credentials_data:
        return None

    try:
        data = json.loads(bytes(source.credentials_data).decode())
    except Exception:
        return None

    refresh_token = data.get("refresh_token")
    if not refresh_token:
        return None

    client_id, _ = _cfg()
    try:
        resp = http.post(
            _TOKEN_URL,
            data={
                "grant_type":    "refresh_token",
                "refresh_token": refresh_token,
                "client_id":     client_id,
            },
            timeout=15,
        )
        resp.raise_for_status()
        new_data = resp.json()
    except Exception:
        return None

    # Spotify may not return a new refresh_token — keep the old one
    if "refresh_token" not in new_data:
        new_data["refresh_token"] = refresh_token

    source.credentials_data = json.dumps(new_data).encode()
    source.save(update_fields=["credentials_data", "updated_at"])
    return new_data.get("access_token")
