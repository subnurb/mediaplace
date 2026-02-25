# MediaPlace

A platform to manage and publish music from multiple streaming platforms, local storage, and FTP servers.

Users connect to **sources** — each source type (SoundCloud, Spotify, YouTube, local disk, FTP…) can hold multiple named accounts. Those connections are then available as inputs and outputs across all tools.

## Platform vision

```
Sources (inputs & outputs)
├── Streaming  → SoundCloud, Spotify, Deezer, YouTube Music
├── Publish    → YouTube (multiple channels)
├── Local      → Local disk paths
└── Remote     → FTP / SFTP servers

Tools (use sources)
├── MP3 to YouTube   ← first tool, available now
├── Playlist sync    ← coming soon
├── Batch converter  ← coming soon
└── ...
```

---

## Stack

| Layer    | Technology                                         |
|----------|----------------------------------------------------|
| Backend  | Django 6 · Python 3.12+ · PostgreSQL               |
| Frontend | React 18 · Redux Toolkit · AdminLTE 4 · Vite       |
| Auth     | Django sessions · Google OAuth 2.0 (per source)    |

---

## Prerequisites

- **Python 3.12+**
- **Node.js 18+**
- **PostgreSQL 14+**
- **FFmpeg** in PATH
  ```bash
  # macOS
  brew install ffmpeg
  # Ubuntu/Debian
  sudo apt install ffmpeg
  # Windows
  winget install FFmpeg
  ```

---

## Setup

### 1 — PostgreSQL

Install and start PostgreSQL, then create the database and user:

```bash
# macOS
brew install postgresql@17
brew services start postgresql@17
export PATH="/usr/local/opt/postgresql@17/bin:$PATH"   # add to ~/.zshrc

# Ubuntu/Debian
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

Create the database and user:

```bash
createdb mediaplace
createuser mediaplace
psql -c "ALTER USER mediaplace WITH PASSWORD 'yourpassword';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE mediaplace TO mediaplace;"
```

Add the credentials to `backend/config/settings_private.py` (copy from `settings_private.example.py`):

```python
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
```

---

### 3 — Google Cloud (YouTube publish source)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → **APIs & Services → Library** → enable **YouTube Data API v3**
3. **APIs & Services → Credentials → Create OAuth client ID**
   - Type: **Web application**
   - Authorized redirect URI: `http://localhost:8000/api/auth/callback/`
4. Download the JSON → rename it `client_secrets.json` → place it in `backend/`
5. **APIs & Services → OAuth consent screen**
   - Add scope: `https://www.googleapis.com/auth/youtube.upload`
   - Add your Google account as a **test user**

### 4 — Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt --prefer-binary
python manage.py migrate
python manage.py runserver
```

Django runs at **http://localhost:8000**

### 5 — Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite runs at **http://localhost:5173** and proxies `/api/*` to Django.

---

## Usage

1. Open **http://localhost:5173**
2. Create an account (username + password)
3. In **Sources**, click **Add → YouTube** to connect a YouTube channel
4. Open the **MP3 to YouTube** tool
5. Upload a local audio + cover image, or paste a streaming URL
6. The video is generated locally with FFmpeg, then published to your chosen YouTube channel

---

## Project structure

```
mediaplace/
├── backend/                  Django 6 API
│   ├── config/               settings, urls, wsgi
│   ├── api/
│   │   ├── models.py         SourceConnection, PendingJob
│   │   ├── views.py          REST endpoints
│   │   └── urls.py
│   ├── youtube_uploader.py   Google OAuth + YouTube upload
│   ├── video_creator.py      FFmpeg video assembly
│   ├── url_downloader.py     yt-dlp audio + cover download
│   ├── ffmpeg_utils.py       FFmpeg path discovery
│   └── client_secrets.json   ← you provide this
│
└── frontend/                 React + Vite
    └── src/
        ├── store/            Redux slices (auth, sources, job)
        ├── pages/            Dashboard, AuthPage
        └── components/       Layout, JobStatus, upload tabs
```

---

## Data model

```
User
 └─ SourceConnection (many)    source_type, name, credentials_data, config
     source_type values:
       youtube_publish          Google OAuth — YouTube upload
       soundcloud               (coming soon)
       spotify                  (coming soon)
       deezer                   (coming soon)
       local                    local disk path
       ftp                      FTP / SFTP server

 └─ PendingJob (many)          video ready to download / publish
```

---

## Development utilities

### Reset test data

Wipe all sync jobs, tracks, library playlists, audio cache and fingerprints while keeping users and their connected platform accounts (SourceConnections).

```bash
cd backend
source .venv/bin/activate

# Preview what would be deleted (no changes made)
python manage.py flush_test_data --dry-run

# Interactive — prompts for confirmation
python manage.py flush_test_data

# Non-interactive (CI / scripts)
python manage.py flush_test_data --yes
```

**Deleted:** `SyncJob`, `SyncTrack`, `LibraryPlaylist`, `LibraryEntry`, `TrackSource`, `AudioFingerprint`, `CachedAudio` (rows + files on disk), `PendingJob`

**Kept:** `User`, `SourceConnection` (all OAuth accounts remain connected)

---

## Environment variables

| Variable              | Default                                    | Description                              |
|-----------------------|--------------------------------------------|------------------------------------------|
| `DB_NAME`             | `mediaplace`                               | PostgreSQL database name                 |
| `DB_USER`             | `mediaplace`                               | PostgreSQL user                          |
| `DB_PASSWORD`         | _(empty)_                                  | PostgreSQL password                      |
| `DB_HOST`             | `localhost`                                | PostgreSQL host                          |
| `DB_PORT`             | `5432`                                     | PostgreSQL port                          |
| `DJANGO_SECRET_KEY`   | dev key                                    | Set a strong random value in production  |
| `OAUTH_REDIRECT_URI`  | `http://localhost:8000/api/auth/callback/` | Must match Google Console                |
| `FRONTEND_URL`        | `http://localhost:5173`                    | Where to redirect after OAuth            |
