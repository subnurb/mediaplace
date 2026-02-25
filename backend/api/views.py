import json
import os
import urllib.parse
import uuid
from functools import wraps

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import FileResponse, HttpResponseRedirect, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from api.models import PendingJob, SourceConnection, UserProfile
from url_downloader import download_from_url
from video_creator import create_video
from youtube_uploader import exchange_code_for_user, get_auth_url, upload_video_for_source
import soundcloud_auth
import google_auth

UPLOAD_DIR = settings.UPLOAD_DIR
OUTPUT_DIR = settings.OUTPUT_DIR

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

FRONTEND_URL = getattr(settings, "FRONTEND_URL", "http://localhost:5173")


# ── Helpers ───────────────────────────────────────────────────────────────────

def require_login(f):
    """Return 401 if the request user is not authenticated."""
    @wraps(f)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Login required"}, status=401)
        return f(request, *args, **kwargs)
    return wrapper


def _user_sources(user):
    return [s.to_dict() for s in user.sources.all()]


def _me_payload(user):
    pending = PendingJob.objects.filter(user=user).first()
    return {
        "user": {"id": user.id, "username": user.username, "email": user.email},
        "sources": _user_sources(user),
        "pending_job": pending.to_dict() if pending else None,
    }


# ── App authentication ────────────────────────────────────────────────────────

@csrf_exempt
def app_register(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body)
        username = data.get("username", "").strip()
        email = data.get("email", "").strip()
        password = data.get("password", "")

        if not username or not password:
            return JsonResponse({"error": "Username and password are required."}, status=400)
        if len(password) < 6:
            return JsonResponse({"error": "Password must be at least 6 characters."}, status=400)
        if User.objects.filter(username=username).exists():
            return JsonResponse({"error": "Username already taken."}, status=400)
        if email and User.objects.filter(email=email).exists():
            return JsonResponse({"error": "Email already registered."}, status=400)

        user = User.objects.create_user(username=username, email=email, password=password)
        login(request, user)

        return JsonResponse({
            "user": {"id": user.id, "username": user.username, "email": user.email},
            "sources": [],
        }, status=201)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def app_login(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body)
        identifier = data.get("username", "").strip()
        password = data.get("password", "")

        # Try username first; if that fails and the identifier looks like an email, try by email
        user = authenticate(request, username=identifier, password=password)
        if user is None and "@" in identifier:
            try:
                matched = User.objects.get(email__iexact=identifier)
                user = authenticate(request, username=matched.username, password=password)
            except User.DoesNotExist:
                pass
        if user is None:
            return JsonResponse({"error": "Invalid username/email or password."}, status=401)

        login(request, user)
        return JsonResponse(_me_payload(user))
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_login
def app_logout(request):
    logout(request)
    return JsonResponse({"success": True})


@require_login
def me(request):
    return JsonResponse(_me_payload(request.user))


@csrf_exempt
@require_login
def update_profile(request):
    """PUT /api/auth/profile/ — update username and/or email."""
    if request.method != "PUT":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body)
        user = request.user

        username = data.get("username", "").strip()
        email = data.get("email", "").strip()

        if username and username != user.username:
            if User.objects.filter(username=username).exclude(id=user.id).exists():
                return JsonResponse({"error": "Username already taken."}, status=400)
            user.username = username

        if email != user.email:
            if email and User.objects.filter(email=email).exclude(id=user.id).exists():
                return JsonResponse({"error": "Email already registered."}, status=400)
            user.email = email

        user.save()
        return JsonResponse({"user": {"id": user.id, "username": user.username, "email": user.email}})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_login
def change_password(request):
    """POST /api/auth/change-password/ — verify current password and set a new one."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body)
        current_password = data.get("current_password", "")
        new_password = data.get("new_password", "")

        if not current_password or not new_password:
            return JsonResponse({"error": "Current and new password are required."}, status=400)
        if len(new_password) < 6:
            return JsonResponse({"error": "Password must be at least 6 characters."}, status=400)

        if not request.user.check_password(current_password):
            return JsonResponse({"error": "Current password is incorrect."}, status=400)

        request.user.set_password(new_password)
        request.user.save()
        login(request, request.user)  # keep session valid after password change
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ── Sources ───────────────────────────────────────────────────────────────────

@require_login
def sources_list(request):
    """GET /api/sources/ — list all source connections for the current user."""
    return JsonResponse({"sources": _user_sources(request.user)})


@csrf_exempt
@require_login
def source_detail(request, source_id):
    """DELETE /api/sources/<id>/ — remove a source connection."""
    if request.method != "DELETE":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        source = request.user.sources.get(id=source_id)
        source.delete()
        return JsonResponse({"success": True})
    except SourceConnection.DoesNotExist:
        return JsonResponse({"error": "Source not found"}, status=404)


# ── YouTube OAuth ─────────────────────────────────────────────────────────────

@require_login
def youtube_connect(request):
    """Start the Google OAuth flow for a YouTube (publish) source."""
    try:
        auth_url, _state = get_auth_url(request.user)
    except FileNotFoundError as e:
        return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"auth_url": auth_url})


def youtube_callback(request):
    """Handle the Google OAuth2 redirect. Recovers the user from the state param."""
    state = request.GET.get("state", "")

    # State format: "<user_id>.<random_token>"
    try:
        user_id = int(state.split(".")[0])
        user = User.objects.get(id=user_id)
    except (ValueError, IndexError, User.DoesNotExist):
        return HttpResponseRedirect(f"{FRONTEND_URL}/?auth_error=invalid_state")

    try:
        action, name = exchange_code_for_user(user, request.build_absolute_uri(), state)
    except Exception as e:
        return HttpResponseRedirect(f"{FRONTEND_URL}/?auth_error={urllib.parse.quote(str(e))}")

    params = urllib.parse.urlencode({"youtube": action, "name": name})
    return HttpResponseRedirect(f"{FRONTEND_URL}/?{params}")


# ── SoundCloud OAuth ──────────────────────────────────────────────────────────

@require_login
def soundcloud_connect(request):
    """Start the SoundCloud OAuth flow."""
    try:
        auth_url, _state = soundcloud_auth.get_auth_url(request.user)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"auth_url": auth_url})


def soundcloud_callback(request):
    """Handle the SoundCloud OAuth redirect. Recovers the user from the state param."""
    state = request.GET.get("state", "")
    code = request.GET.get("code", "")

    # State format: "<user_id>.<random_token>"
    try:
        user_id = int(state.split(".")[0])
        user = User.objects.get(id=user_id)
    except (ValueError, IndexError, User.DoesNotExist):
        return HttpResponseRedirect(f"{FRONTEND_URL}/?auth_error=invalid_state")

    if not code:
        return HttpResponseRedirect(f"{FRONTEND_URL}/?auth_error=no_code")

    try:
        action, name = soundcloud_auth.exchange_code_for_user(user, code)
    except Exception as e:
        return HttpResponseRedirect(f"{FRONTEND_URL}/?auth_error={urllib.parse.quote(str(e))}")

    params = urllib.parse.urlencode({"soundcloud": action, "name": name})
    return HttpResponseRedirect(f"{FRONTEND_URL}/?{params}")


# ── Google sign-in OAuth ───────────────────────────────────────────────────────

def google_login(request):
    """Return a Google OAuth URL for sign-in (no account required yet)."""
    try:
        auth_url, state = google_auth.get_login_url()
    except FileNotFoundError as e:
        return JsonResponse({"error": str(e)}, status=400)
    # Store state in session for CSRF verification in the callback
    request.session["google_login_state"] = state
    return JsonResponse({"auth_url": auth_url})


def google_callback(request):
    """Handle the Google OAuth2 redirect for sign-in.

    Creates or retrieves a User linked to the Google account, then logs them in.
    """
    state = request.GET.get("state", "")
    expected_state = request.session.pop("google_login_state", None)
    if not expected_state or state != expected_state:
        return HttpResponseRedirect(f"{FRONTEND_URL}/?auth_error=invalid_state")

    try:
        info = google_auth.get_user_info(request.build_absolute_uri(), state=state)
    except Exception as e:
        return HttpResponseRedirect(f"{FRONTEND_URL}/?auth_error={urllib.parse.quote(str(e))}")

    google_id = info["google_id"]
    email = info["email"]
    name = info.get("name", "")

    # 1. Look up by google_id
    profile = UserProfile.objects.filter(google_id=google_id).select_related("user").first()
    if profile:
        user = profile.user
    else:
        # 2. Look up by email — link the existing account
        if email:
            try:
                user = User.objects.get(email__iexact=email)
                UserProfile.objects.update_or_create(user=user, defaults={"google_id": google_id})
            except User.DoesNotExist:
                user = None
        else:
            user = None

        # 3. No existing account — create one
        if user is None:
            base = (email.split("@")[0] if email else name.replace(" ", "").lower()) or "user"
            # Sanitize to valid username characters
            base = "".join(c for c in base if c.isalnum() or c in "_-")[:30] or "user"
            username = base
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base}{counter}"
                counter += 1
            user = User.objects.create_user(username=username, email=email, password=None)
            UserProfile.objects.create(user=user, google_id=google_id)

    user.backend = "django.contrib.auth.backends.ModelBackend"
    login(request, user)
    return HttpResponseRedirect(f"{FRONTEND_URL}/?google=login")


# ── Jobs ──────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_login
def job_upload_file(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        audio = request.FILES["audio"]
        image = request.FILES["image"]
        title = request.POST["title"]
        description = request.POST.get("description", "")
        tags = [t.strip() for t in request.POST.get("tags", "").split(",") if t.strip()]
        privacy = request.POST.get("privacy", "unlisted")
        animation = request.POST.get("animation", "none")

        job_id = uuid.uuid4().hex[:8]
        audio_path = os.path.join(UPLOAD_DIR, f"{job_id}_audio{os.path.splitext(audio.name)[1]}")
        image_path = os.path.join(UPLOAD_DIR, f"{job_id}_image{os.path.splitext(image.name)[1]}")

        for path, fileobj in ((audio_path, audio), (image_path, image)):
            with open(path, "wb") as f:
                for chunk in fileobj.chunks():
                    f.write(chunk)

        source_id = request.POST.get("source_id")
        source = None
        if source_id:
            try:
                source = request.user.sources.get(
                    id=int(source_id),
                    source_type=SourceConnection.SourceType.YOUTUBE_PUBLISH,
                )
            except (SourceConnection.DoesNotExist, ValueError):
                pass

        video_path = os.path.join(OUTPUT_DIR, f"{job_id}_video.mp4")
        create_video(image_path, audio_path, video_path, animation=animation)

        PendingJob.objects.filter(user=request.user).delete()
        job = PendingJob.objects.create(
            user=request.user,
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            privacy=privacy,
            source=source,
        )

        return JsonResponse({"video_ready": True, "job": job.to_dict()})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_login
def job_upload_url(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    try:
        data = json.loads(request.body)
        music_url = data["music_url"]
        title = data.get("title", "").strip()
        description = data.get("description", "")
        tags = [t.strip() for t in data.get("tags", "").split(",") if t.strip()]
        privacy = data.get("privacy", "unlisted")
        animation = data.get("animation", "none")

        job_id = uuid.uuid4().hex[:8]
        job_dir = os.path.join(UPLOAD_DIR, job_id)
        result = download_from_url(music_url, job_dir)

        if not result["image_path"]:
            return JsonResponse(
                {"error": "Could not fetch cover image from this URL."}, status=422
            )

        if not title:
            title = result["title"]

        source_id = data.get("source_id")
        source = None
        if source_id:
            try:
                source = request.user.sources.get(
                    id=int(source_id),
                    source_type=SourceConnection.SourceType.YOUTUBE_PUBLISH,
                )
            except (SourceConnection.DoesNotExist, ValueError):
                pass

        video_path = os.path.join(OUTPUT_DIR, f"{job_id}_video.mp4")
        create_video(result["image_path"], result["audio_path"], video_path, animation=animation)

        PendingJob.objects.filter(user=request.user).delete()
        job = PendingJob.objects.create(
            user=request.user,
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            privacy=privacy,
            source=source,
        )

        return JsonResponse({"video_ready": True, "job": job.to_dict()})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@require_login
def job_download(request):
    job = PendingJob.objects.filter(user=request.user).first()
    if not job or not os.path.exists(job.video_path):
        return JsonResponse({"error": "No video available"}, status=404)
    safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in job.title)
    return FileResponse(open(job.video_path, "rb"), as_attachment=True, filename=f"{safe_name}.mp4")


@csrf_exempt
@require_login
def job_publish(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    job = PendingJob.objects.filter(user=request.user).first()
    if not job:
        return JsonResponse({"error": "No video to publish."}, status=400)

    # Use the channel stored on the job; fall back to the first connected channel
    source = job.source if job.source_id else request.user.sources.filter(
        source_type=SourceConnection.SourceType.YOUTUBE_PUBLISH,
        is_active=True,
    ).first()
    if not source or source.get_credentials() is None:
        return JsonResponse({"error": "YouTube not connected."}, status=403)

    try:
        video_id = upload_video_for_source(
            source, job.video_path, job.title, job.description, job.tags, job.privacy
        )
        job.delete()
        return JsonResponse({"success": True, "video_id": video_id})
    except Exception as e:
        error_str = str(e)
        if "youtubeSignupRequired" in error_str:
            return JsonResponse({"youtube_signup_required": True}, status=403)
        return JsonResponse({"error": error_str}, status=500)
