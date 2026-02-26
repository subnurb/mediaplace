# ── Private / local settings — EXAMPLE ────────────────────────────────────────
# Copy this file to settings_private.py and fill in your values.
# settings_private.py is gitignored and must never be committed.

# Django
SECRET_KEY = "replace-with-a-long-random-string"

# PostgreSQL database
# Create with:
#   createdb mediaplace
#   createuser mediaplace
#   psql -c "ALTER USER mediaplace WITH PASSWORD 'yourpassword';"
#   psql -c "GRANT ALL PRIVILEGES ON DATABASE mediaplace TO mediaplace;"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "mediaplace",
        "USER": "mediaplace",
        "PASSWORD": "yourpassword",
        "HOST": "localhost",
        "PORT": "5432",
    }
}

# Frontend URL (where to redirect after OAuth)
FRONTEND_URL = "http://localhost:5173"

# Google / YouTube OAuth
# Both URIs must be listed under Google Cloud Console > Credentials > Authorized redirect URIs
OAUTH_REDIRECT_URI = "http://localhost:8000/api/auth/callback/"
GOOGLE_LOGIN_REDIRECT_URI = "http://localhost:8000/api/auth/google/callback/"

# SoundCloud OAuth
# Register your app at https://developers.soundcloud.com/
# Redirect URI must be registered in the SoundCloud app settings
SOUNDCLOUD_CLIENT_ID = "your_soundcloud_client_id"
SOUNDCLOUD_CLIENT_SECRET = "your_soundcloud_client_secret"
SOUNDCLOUD_REDIRECT_URI = "http://localhost:8000/api/auth/soundcloud/callback/"

# Spotify OAuth (PKCE — no client secret needed for token exchange)
# Register your app at https://developer.spotify.com/dashboard
# Add redirect URI: http://localhost:8000/api/auth/spotify/callback/
SPOTIFY_CLIENT_ID = "your_spotify_client_id"
SPOTIFY_REDIRECT_URI = "http://localhost:8000/api/auth/spotify/callback/"
