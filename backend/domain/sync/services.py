"""Pure domain services for the Sync bounded context.

Functions here encapsulate business rules around playlist sync jobs,
track status transitions, and push planning. No I/O.
"""

# Status constants mirroring SyncTrack.Status choices
STATUS_MATCHED = "matched"
STATUS_UNCERTAIN = "uncertain"
STATUS_NOT_FOUND = "not_found"
STATUS_UPLOADED = "uploaded"
STATUS_SKIPPED = "skipped"
STATUS_FAILED = "failed"

PUSHABLE_STATUSES = {STATUS_MATCHED, STATUS_UPLOADED}
PUSHABLE_FEEDBACKS = {"confirmed"}


def is_track_pushable(status, user_feedback, target_video_id):
    """Decide whether a track should be included in a playlist push.

    A track is pushable when:
    - It has a matched/uploaded status with a target ID, OR
    - The user explicitly confirmed it (regardless of auto-status).
    """
    if not target_video_id:
        return False
    if status in PUSHABLE_STATUSES:
        return True
    if user_feedback in PUSHABLE_FEEDBACKS:
        return True
    return False


def compute_push_plan(tracks):
    """Given a list of track dicts, return those eligible for push.

    Args:
        tracks: list of dicts with keys:
            status, user_feedback, target_video_id, pushed_to_playlist, source_title

    Returns:
        list of track dicts that should be pushed (excludes already-pushed).
    """
    result = []
    for t in tracks:
        if t.get("pushed_to_playlist"):
            continue
        if is_track_pushable(t["status"], t.get("user_feedback", ""),
                             t.get("target_video_id", "")):
            result.append(t)
    return result


def classify_sync_error(error_message):
    """Map a raw error string to a structured domain error category.

    Returns:
        (category: str, user_message: str)
    """
    msg = (error_message or "").lower()

    if "403" in msg and "may not be registered" in msg:
        return (
            "spotify_not_allowlisted",
            "This Spotify account is not allowed to use this app. "
            "In Development Mode the app owner must add your Spotify account "
            'under "Users and access" in the Spotify Developer Dashboard.',
        )

    if "403" in msg and "/v1/me" in msg:
        return (
            "spotify_not_allowlisted",
            "Spotify connection failed: this Spotify account is not allowed. "
            "The app owner must add your account in the Spotify Developer Dashboard.",
        )

    if "token" in msg and ("expired" in msg or "invalid" in msg):
        return (
            "token_expired",
            "Your connection token has expired. Please reconnect the source.",
        )

    if "rate limit" in msg or "429" in msg:
        return (
            "rate_limited",
            "The platform rate-limited the request. Please try again later.",
        )

    return ("unknown", "An unexpected error occurred during sync.")
