"""SoundCloud OAuth 2.1 helpers (PKCE required as of Oct 2024).

Credentials are read from Django settings (config/settings_private.py):
  SOUNDCLOUD_CLIENT_ID
  SOUNDCLOUD_CLIENT_SECRET
  SOUNDCLOUD_REDIRECT_URI  (optional — defaults to localhost)

The redirect URI must also be registered in the SoundCloud app settings.
See https://developers.soundcloud.com/docs/api/guide
"""

import base64
import hashlib
import json
import os
import urllib.parse

import requests as http

_AUTHORIZE_URL = "https://secure.soundcloud.com/authorize"
_TOKEN_URL = "https://secure.soundcloud.com/oauth/token"
_ME_URL = "https://api.soundcloud.com/me"


def _cfg():
    """Return (client_id, client_secret, redirect_uri) from Django settings."""
    from django.conf import settings
    return (
        getattr(settings, "SOUNDCLOUD_CLIENT_ID", ""),
        getattr(settings, "SOUNDCLOUD_CLIENT_SECRET", ""),
        getattr(settings, "SOUNDCLOUD_REDIRECT_URI",
                "http://localhost:8000/api/auth/soundcloud/callback/"),
    )


def _pkce_pair():
    """Return (code_verifier, code_challenge) for PKCE S256 (required by OAuth 2.1)."""
    verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def get_auth_url(user):
    """Return (auth_url, state) to redirect the user to SoundCloud's consent screen.

    State format: "{user_id}.{code_verifier}" so the callback can pass code_verifier
    into the token exchange (PKCE required by SoundCloud OAuth 2.1).
    """
    client_id, client_secret, redirect_uri = _cfg()
    if not client_id or not client_secret:
        raise ValueError(
            "SoundCloud credentials not configured. "
            "Set SOUNDCLOUD_CLIENT_ID and SOUNDCLOUD_CLIENT_SECRET in settings_private.py."
        )
    verifier, challenge = _pkce_pair()
    state = f"{user.id}.{verifier}"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "non-expiring",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        # Force SoundCloud to show the login form even when the user has an
        # active session, allowing them to sign in as a different account.
        "display": "popup",
    }
    auth_url = f"{_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"
    return auth_url, state


def exchange_code_for_user(user, code, code_verifier):
    """Exchange an authorization code + PKCE verifier for an access token and persist as a SourceConnection.

    Deduplicates by SoundCloud user ID stored in config, so reconnecting the
    same account updates the token in place.
    """
    from api.models import SourceConnection

    client_id, client_secret, redirect_uri = _cfg()

    # Exchange code + code_verifier (PKCE) → token (OAuth 2.1)
    resp = http.post(
        _TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "code": code,
            "code_verifier": code_verifier,
        },
        timeout=15,
    )
    resp.raise_for_status()
    token_data = resp.json()
    access_token = token_data["access_token"]

    # Fetch the user's SoundCloud profile to get username + stable ID (Bearer per API guide)
    me_resp = http.get(
        _ME_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    me_resp.raise_for_status()
    profile = me_resp.json()

    sc_username = profile.get("username", "SoundCloud")
    sc_user_id = str(profile.get("id", ""))
    sc_permalink = profile.get("permalink", "")

    credentials_bytes = json.dumps(token_data).encode()

    if sc_user_id:
        # Deduplicate: same SoundCloud account → update existing connection
        existing = SourceConnection.objects.filter(
            user=user,
            source_type=SourceConnection.SourceType.SOUNDCLOUD,
            config__sc_user_id=sc_user_id,
        ).first()
        if existing:
            existing.credentials_data = credentials_bytes
            existing.name = sc_username
            existing.is_active = True
            existing.save(update_fields=["credentials_data", "name", "is_active", "updated_at"])
            return "updated", sc_username

        SourceConnection.objects.create(
            user=user,
            source_type=SourceConnection.SourceType.SOUNDCLOUD,
            name=sc_username,
            credentials_data=credentials_bytes,
            config={"sc_user_id": sc_user_id, "permalink": sc_permalink},
        )
        return "new", sc_username
    else:
        # Fallback when profile fetch returned no ID — always create a new entry
        SourceConnection.objects.create(
            user=user,
            source_type=SourceConnection.SourceType.SOUNDCLOUD,
            name=sc_username,
            credentials_data=credentials_bytes,
            is_active=True,
        )
        return "new", sc_username


def get_access_token(source):
    """Return the stored access token string for a SoundCloud SourceConnection, or None."""
    if not source.credentials_data:
        return None
    try:
        data = json.loads(bytes(source.credentials_data).decode())
        return data.get("access_token")
    except Exception:
        return None


def refresh_access_token(source):
    """Attempt to refresh the SoundCloud access token using the stored refresh_token.

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

    client_id, client_secret, _ = _cfg()
    try:
        resp = http.post(
            _TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
            },
            timeout=15,
        )
        resp.raise_for_status()
        new_token_data = resp.json()
    except Exception:
        return None

    # Preserve existing refresh_token if not returned in the new response
    if "refresh_token" not in new_token_data:
        new_token_data["refresh_token"] = refresh_token

    source.credentials_data = json.dumps(new_token_data).encode()
    source.save(update_fields=["credentials_data", "updated_at"])
    return new_token_data.get("access_token")
