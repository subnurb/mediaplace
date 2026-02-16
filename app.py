import os
import uuid

from flask import Flask, redirect, render_template, request, send_file, session, url_for

from url_downloader import download_from_url
from video_creator import create_video
from youtube_uploader import (
    exchange_code,
    get_auth_url,
    is_authenticated,
    logout,
    upload_video,
)

app = Flask(__name__)
app.secret_key = os.urandom(24)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


@app.route("/")
def index():
    authenticated = is_authenticated()
    return render_template("index.html", authenticated=authenticated)


@app.route("/login")
def login():
    """Start the Google OAuth2 flow."""
    try:
        auth_url, state = get_auth_url()
    except FileNotFoundError as e:
        return render_template("index.html", authenticated=False, error=str(e))
    session["oauth_state"] = state
    return redirect(auth_url)


@app.route("/oauth2callback")
def oauth2callback():
    """Handle the Google OAuth2 callback."""
    exchange_code(request.url)
    return redirect(url_for("index"))


@app.route("/logout")
def logout_route():
    """Remove saved credentials."""
    logout()
    return redirect(url_for("index"))


@app.route("/upload", methods=["POST"])
def upload():
    if not is_authenticated():
        return redirect(url_for("login"))

    try:
        audio = request.files["audio"]
        image = request.files["image"]
        title = request.form["title"]
        description = request.form.get("description", "")
        tags_raw = request.form.get("tags", "")
        privacy = request.form.get("privacy", "unlisted")

        animation = request.form.get("animation", "none")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

        # Save uploaded files
        job_id = uuid.uuid4().hex[:8]
        audio_ext = os.path.splitext(audio.filename)[1]
        image_ext = os.path.splitext(image.filename)[1]
        audio_path = os.path.join(UPLOAD_DIR, f"{job_id}_audio{audio_ext}")
        image_path = os.path.join(UPLOAD_DIR, f"{job_id}_image{image_ext}")
        audio.save(audio_path)
        image.save(image_path)

        # Create video
        video_path = os.path.join(OUTPUT_DIR, f"{job_id}_video.mp4")
        create_video(image_path, audio_path, video_path, animation=animation)

        # Save job in session so user can download or publish
        session["pending_job"] = {
            "video_path": video_path,
            "title": title,
            "description": description,
            "tags": tags,
            "privacy": privacy,
        }

        return render_template(
            "index.html", authenticated=True, video_ready=True,
            form_data=session["pending_job"],
        )

    except Exception as e:
        return render_template("index.html", authenticated=True, error=str(e))


@app.route("/upload-url", methods=["POST"])
def upload_url():
    if not is_authenticated():
        return redirect(url_for("login"))

    try:
        music_url = request.form["music_url"]
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "")
        tags_raw = request.form.get("tags", "")
        privacy = request.form.get("privacy", "unlisted")

        animation = request.form.get("animation", "none")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

        job_id = uuid.uuid4().hex[:8]
        job_dir = os.path.join(UPLOAD_DIR, job_id)

        # Download audio and cover from URL
        result = download_from_url(music_url, job_dir)

        if not result["image_path"]:
            return render_template(
                "index.html", authenticated=True, active_tab="url",
                error="Could not fetch cover image from this URL.",
            )

        # Use fetched title if user didn't provide one
        if not title:
            title = result["title"]

        # Create video
        video_path = os.path.join(OUTPUT_DIR, f"{job_id}_video.mp4")
        create_video(result["image_path"], result["audio_path"], video_path, animation=animation)

        # Save job in session so user can download or publish
        session["pending_job"] = {
            "video_path": video_path,
            "title": title,
            "description": description,
            "tags": tags,
            "privacy": privacy,
        }

        return render_template(
            "index.html", authenticated=True, active_tab="url",
            video_ready=True, form_data=session["pending_job"],
        )

    except Exception as e:
        return render_template(
            "index.html", authenticated=True, active_tab="url", error=str(e),
        )


@app.route("/download")
def download():
    """Download the generated video file."""
    pending = session.get("pending_job")
    if not pending or not os.path.exists(pending["video_path"]):
        return redirect(url_for("index"))

    title = pending.get("title", "video")
    safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
    return send_file(
        pending["video_path"],
        as_attachment=True,
        download_name=f"{safe_name}.mp4",
    )


@app.route("/publish", methods=["POST"])
def publish():
    """Upload the previously generated video to YouTube."""
    if not is_authenticated():
        return redirect(url_for("login"))

    pending = session.get("pending_job")
    if not pending:
        return render_template(
            "index.html", authenticated=True,
            error="No video to publish. Please generate a video first.",
        )

    try:
        video_id = upload_video(
            pending["video_path"],
            pending["title"],
            pending["description"],
            pending["tags"],
            pending["privacy"],
        )
        session.pop("pending_job", None)
        return render_template(
            "index.html", authenticated=True, success=True, video_id=video_id,
        )
    except Exception as e:
        error_str = str(e)
        if "youtubeSignupRequired" in error_str:
            return render_template(
                "index.html", authenticated=True,
                youtube_signup_required=True, has_pending_job=True,
            )
        return render_template(
            "index.html", authenticated=True, video_ready=True,
            form_data=pending, error=error_str,
        )


@app.route("/retry", methods=["POST"])
def retry():
    """Retry uploading (alias for /publish)."""
    return publish()


if __name__ == "__main__":
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # Allow HTTP for localhost
    app.run(debug=True, port=5000)
