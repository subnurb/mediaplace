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
# When frontend runs with HTTPS (Vite with certs): use https://localhost:5173

# Google / YouTube OAuth
# Both URIs must be listed under Google Cloud Console > Credentials > Authorized redirect URIs
OAUTH_REDIRECT_URI = "http://localhost:8000/api/auth/callback/"
GOOGLE_LOGIN_REDIRECT_URI = "http://localhost:8000/api/auth/google/callback/"
# When backend runs with HTTPS (runsslserver), use https and add the https URIs in Google Console:
# OAUTH_REDIRECT_URI = "https://localhost:8000/api/auth/callback/"
# GOOGLE_LOGIN_REDIRECT_URI = "https://localhost:8000/api/auth/google/callback/"

# SoundCloud OAuth
# Register your app at https://developers.soundcloud.com/
# Redirect URI must be registered in the SoundCloud app settings
SOUNDCLOUD_CLIENT_ID = "your_soundcloud_client_id"
SOUNDCLOUD_CLIENT_SECRET = "your_soundcloud_client_secret"
SOUNDCLOUD_REDIRECT_URI = "http://localhost:8000/api/auth/soundcloud/callback/"

# Spotify OAuth (PKCE — no client secret needed for token exchange)
# Register your app at https://developer.spotify.com/dashboard
# Spotify does not allow "localhost"; use 127.0.0.1 (see redirect_uri docs).
# Add this exact URI in the Dashboard: http://127.0.0.1:8000/api/auth/spotify/callback/
# For HTTPS backend (runsslserver): https://127.0.0.1:8000/api/auth/spotify/callback/
SPOTIFY_CLIENT_ID = "your_spotify_client_id"
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8000/api/auth/spotify/callback/"

# Optional: redirect HTTP → HTTPS in development (run runserver 8000 + runsslserver 8443)
# USE_HTTPS_DEV_REDIRECT = True
# HTTPS_DEV_PORT = 8443

# Invitation code required to create an account (set to "" to disable)
# INVITATION_CODE = "CHANGE_ME"
