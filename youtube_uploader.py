import os
import pickle

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRETS_FILE = os.path.join(os.path.dirname(__file__), "client_secrets.json")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.pickle")
REDIRECT_URI = "http://localhost:5000/oauth2callback"


def get_auth_url():
    """Build and return the Google OAuth2 authorization URL."""
    if not os.path.exists(CLIENT_SECRETS_FILE):
        raise FileNotFoundError(
            "client_secrets.json not found. "
            "Please download it from Google Cloud Console. "
            "See README.md for instructions."
        )
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI
    )
    auth_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    return auth_url, state


def exchange_code(authorization_response):
    """Exchange the OAuth2 callback code for credentials and save them."""
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI
    )
    flow.fetch_token(authorization_response=authorization_response)
    credentials = flow.credentials

    with open(TOKEN_FILE, "wb") as f:
        pickle.dump(credentials, f)

    return credentials


def get_credentials():
    """Load saved credentials, refreshing if needed. Returns None if not authenticated."""
    if not os.path.exists(TOKEN_FILE):
        return None

    with open(TOKEN_FILE, "rb") as f:
        credentials = pickle.load(f)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            with open(TOKEN_FILE, "wb") as f:
                pickle.dump(credentials, f)
        else:
            return None

    return credentials


def is_authenticated():
    """Check whether valid YouTube credentials exist."""
    return get_credentials() is not None


def logout():
    """Remove saved credentials."""
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)


def upload_video(video_path, title, description="", tags=None, privacy="unlisted"):
    """Upload a video to YouTube and return the video ID."""
    credentials = get_credentials()
    if credentials is None:
        raise RuntimeError("Not authenticated. Please sign in with Google first.")

    youtube = build("youtube", "v3", credentials=credentials)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": "10",  # Music category
        },
        "status": {
            "privacyStatus": privacy,
        },
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        _, response = request.next_chunk()

    video_id = response["id"]
    return video_id
