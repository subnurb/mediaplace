"""Google OAuth2 flow for user sign-in (not YouTube channel connection).

Uses the same client_secrets.json as youtube_uploader.py but requests only
identity/email scopes, producing a lightweight sign-in-with-Google flow.

Redirect URI: GOOGLE_LOGIN_REDIRECT_URI (default: /api/auth/google/callback/)
This URI must be added to your Google Cloud Console OAuth 2.0 credentials.
"""

import json
import os
import secrets
import ssl
import urllib.request

from google_auth_oauthlib.flow import Flow

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

CLIENT_SECRETS_FILE = os.path.join(os.path.dirname(__file__), "client_secrets.json")


def _redirect_uri():
    from django.conf import settings
    return getattr(
        settings,
        "GOOGLE_LOGIN_REDIRECT_URI",
        "http://localhost:8000/api/auth/google/callback/",
    )


def get_login_url():
    """Return (auth_url, state) for a Google sign-in flow."""
    if not os.path.exists(CLIENT_SECRETS_FILE):
        raise FileNotFoundError(
            "client_secrets.json not found. Download it from Google Cloud Console."
        )
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=_redirect_uri()
    )
    state = secrets.token_urlsafe(32)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="select_account",
        state=state,
    )
    return auth_url, state


def get_user_info(authorization_response, state=None):
    """Exchange the OAuth2 callback and return Google user info.

    Returns a dict with keys: google_id, email, name
    Raises on failure.
    """
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=_redirect_uri(), state=state
    )
    flow.fetch_token(authorization_response=authorization_response)
    credentials = flow.credentials

    # Fetch user info from Google's userinfo endpoint
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {credentials.token}"},
    )
    with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
        info = json.loads(resp.read().decode("utf-8"))

    return {
        "google_id": info["sub"],
        "email": info.get("email", ""),
        "name": info.get("name", ""),
    }
