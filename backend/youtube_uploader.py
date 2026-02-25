import os
import pickle
import secrets

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# youtube.force-ssl covers full account management (create/edit playlists,
# add playlist items) and is required by playlists.insert + playlistItems.insert.
# youtube.upload covers video uploads.
# youtube.readonly is needed for channels.list(mine=True).
SCOPES = [
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
CLIENT_SECRETS_FILE = os.path.join(os.path.dirname(__file__), "client_secrets.json")


def _redirect_uri():
    """Read OAUTH_REDIRECT_URI from Django settings (set in settings_private.py)."""
    from django.conf import settings
    return getattr(settings, "OAUTH_REDIRECT_URI", "http://localhost:8000/api/auth/callback/")


def get_auth_url(user):
    """Build the Google OAuth2 authorization URL for a user.

    The user ID is embedded in the state so the callback can identify
    which user to associate the credentials with — no extra session key needed.
    """
    if not os.path.exists(CLIENT_SECRETS_FILE):
        raise FileNotFoundError(
            "client_secrets.json not found. Download it from Google Cloud Console."
        )
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=_redirect_uri()
    )
    # state = "<user_id>.<random_token>"
    custom_state = f"{user.id}.{secrets.token_urlsafe(16)}"
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        # "select_account" forces Google to show the account picker so the user
        # can choose a DIFFERENT Google account when connecting a second channel.
        # "consent" forces the permissions screen so a refresh_token is always issued.
        prompt="select_account consent",
        state=custom_state,
    )
    return auth_url, custom_state


def _fetch_channel_info(credentials):
    """Return (channel_title, channel_id) for the authenticated user.

    Falls back to ("YouTube", None) if the API call fails for any reason.
    """
    try:
        youtube = build("youtube", "v3", credentials=credentials)
        response = youtube.channels().list(part="snippet", mine=True).execute()
        items = response.get("items", [])
        if items:
            return items[0]["snippet"]["title"], items[0]["id"]
    except Exception:
        pass
    return "YouTube", None


def exchange_code_for_user(user, authorization_response, state=None):
    """Exchange the OAuth2 callback code for credentials and persist as a SourceConnection.

    Uses the real YouTube channel name and deduplicates by channel_id stored in config,
    so reconnecting the same channel updates it in place rather than creating a duplicate.
    """
    from api.models import SourceConnection

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=_redirect_uri(), state=state
    )
    flow.fetch_token(authorization_response=authorization_response)
    credentials = flow.credentials

    channel_name, channel_id = _fetch_channel_info(credentials)

    if channel_id:
        # Deduplicate: if this channel is already stored, refresh its token and name
        existing = SourceConnection.objects.filter(
            user=user,
            source_type=SourceConnection.SourceType.YOUTUBE_PUBLISH,
            config__channel_id=channel_id,
        ).first()
        if existing:
            existing.credentials_data = pickle.dumps(credentials)
            existing.name = channel_name
            existing.is_active = True
            existing.save(update_fields=["credentials_data", "name", "is_active", "updated_at"])
            return "updated", channel_name

        SourceConnection.objects.create(
            user=user,
            source_type=SourceConnection.SourceType.YOUTUBE_PUBLISH,
            name=channel_name,
            credentials_data=pickle.dumps(credentials),
            config={"channel_id": channel_id},
        )
        return "new", channel_name
    else:
        # channel_id unknown (API call failed) — always create a new entry
        SourceConnection.objects.create(
            user=user,
            source_type=SourceConnection.SourceType.YOUTUBE_PUBLISH,
            name=channel_name,
            credentials_data=pickle.dumps(credentials),
            is_active=True,
        )
        return "new", channel_name


def upload_video_for_source(source, video_path, title, description="", tags=None, privacy="unlisted"):
    """Upload a video to YouTube using a SourceConnection and return the video ID."""
    credentials = source.get_credentials()
    if credentials is None:
        raise RuntimeError("YouTube credentials expired. Please reconnect your account.")

    youtube = build("youtube", "v3", credentials=credentials)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": "10",
        },
        "status": {"privacyStatus": privacy},
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        _, response = request.next_chunk()

    return response["id"]
