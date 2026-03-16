import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "corsheaders",
    # sslserver omitted: we use api.management.commands.runsslserver (Python 3.12+ compatible)
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.middleware.HTTPSRedirectMiddleware",  # HTTP → HTTPS redirect when USE_HTTPS_DEV_REDIRECT
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

ROOT_URLCONF = "config.urls"

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "mediaplace"),
        "USER": os.environ.get("DB_USER", "mediaplace"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# CORS – allow the React dev server
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://localhost:5173",
    "https://localhost:8000",
    "https://localhost:8443",
]
CORS_ALLOW_CREDENTIALS = True

# HTTPS in development (django-sslserver)
# Run: python manage.py runsslserver [port]  (default 8000)
# Optional HTTP→HTTPS redirect: set USE_HTTPS_DEV_REDIRECT = True and run
#   runsslserver 8443  (HTTPS) and  runserver 8000  (HTTP redirects to 8443)
USE_HTTPS_DEV_REDIRECT = False  # set True in settings_private when using two processes
HTTPS_DEV_PORT = int(os.environ.get("HTTPS_DEV_PORT", "8443"))

# Media / upload directories
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
AUDIO_CACHE_DIR = BASE_DIR / "audio_cache"   # permanent full-quality audio cache

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
            ]
        },
    }
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Private setting defaults (overridden by settings_private.py) ──────────────

SECRET_KEY = "dev-secret-change-in-production-abc123xyz"

# Frontend URL — where to redirect the browser after OAuth flows
FRONTEND_URL = "http://localhost:5173"

# Google / YouTube OAuth redirect URI (for YouTube channel connection)
OAUTH_REDIRECT_URI = "http://localhost:8000/api/auth/callback/"

# Google sign-in redirect URI (must also be added to Google Cloud Console)
GOOGLE_LOGIN_REDIRECT_URI = "http://localhost:8000/api/auth/google/callback/"

# SoundCloud OAuth credentials
SOUNDCLOUD_CLIENT_ID = ""
SOUNDCLOUD_CLIENT_SECRET = ""
SOUNDCLOUD_REDIRECT_URI = "http://localhost:8000/api/auth/soundcloud/callback/"

# AcoustID API key — register free at https://acoustid.org/new-application
ACOUSTID_API_KEY = os.environ.get("ACOUSTID_API_KEY", "")

# Number of tracks matched simultaneously during sync analysis (L1+L2+L3)
SYNC_ANALYSIS_PARALLELISM = 5

# ShazamIO audio recognition — runs in a subprocess after fingerprinting.
# shazamio-core (Rust) segfaults on Python 3.14 at module init (pyo3_log bug).
# Leave False until shazamio publishes a Python 3.14-compatible wheel.
SHAZAM_ENABLED = True

# Local (Dejavu-style) audio fingerprint — also runs in a daemon thread.
# Disabled by default: librosa on large files can be slow.
LOCAL_FINGERPRINT_ENABLED = True

# Invitation code — set a non-empty string to require it on registration.
# Leave empty or set to "" to allow open registration.
INVITATION_CODE = ""

# Load local private overrides — copy settings_private.example.py to
# settings_private.py and fill in your values (file is gitignored)
try:
    from config.settings_private import *  # noqa: F401,F403
except ImportError:
    pass

# Allow HTTP for OAuth on localhost (never set this in production)
if DEBUG:
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
