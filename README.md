# MP3 to YouTube Video Uploader

Upload an audio file + cover image to create a video and publish it to YouTube.

## Prerequisites

- **Python 3.8+**
- **FFmpeg** installed and available in PATH
  - Windows: `winget install FFmpeg` or download from https://ffmpeg.org/download.html
  - Mac: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`

## Installation

```bash
pip install -r requirements.txt
```

## YouTube API Setup

You need Google OAuth credentials to upload videos. Follow these steps:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Navigate to **APIs & Services > Library**
4. Search for **YouTube Data API v3** and click **Enable**
5. Go to **APIs & Services > Credentials**
6. Click **Create Credentials > OAuth client ID**
7. If prompted, configure the **OAuth consent screen**:
   - Choose **External** user type
   - Fill in the required fields (app name, email)
   - Add scope: `https://www.googleapis.com/auth/youtube.upload`
   - Add your Google account as a **test user**
8. Back in Credentials, create an **OAuth client ID**:
   - Application type: **Web application**
   - Add `http://localhost:5000/oauth2callback` as an **Authorized redirect URI**
   - Download the JSON file
9. Rename it to `client_secrets.json` and place it in this project's root directory

## Usage

```bash
python app.py
```

1. Open http://localhost:5000 in your browser
2. Click **Sign in with Google** — you'll be redirected to Google to authorize YouTube access
3. Once authenticated, fill in your audio, image, title, and other details
4. Click **Create & Upload**

The token is cached in `token.pickle` so you won't need to sign in again until it expires. You can sign out at any time from the app.
