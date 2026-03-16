"""Tests for domain.sync.services — pure sync business logic."""

from domain.sync.services import (
    classify_sync_error,
    compute_push_plan,
    is_track_pushable,
)


class TestIsTrackPushable:

    def test_matched_with_target_is_pushable(self):
        assert is_track_pushable("matched", "", "vid123") is True

    def test_uploaded_with_target_is_pushable(self):
        assert is_track_pushable("uploaded", "", "vid123") is True

    def test_confirmed_uncertain_is_pushable(self):
        assert is_track_pushable("uncertain", "confirmed", "vid123") is True

    def test_not_found_is_not_pushable(self):
        assert is_track_pushable("not_found", "", "") is False

    def test_matched_without_target_is_not_pushable(self):
        assert is_track_pushable("matched", "", "") is False

    def test_skipped_is_not_pushable(self):
        assert is_track_pushable("skipped", "", "vid123") is False

    def test_rejected_uncertain_is_not_pushable(self):
        assert is_track_pushable("uncertain", "rejected", "vid123") is False


class TestComputePushPlan:

    def test_filters_pushable_tracks(self):
        tracks = [
            {"status": "matched", "user_feedback": "", "target_video_id": "v1",
             "pushed_to_playlist": False, "source_title": "A"},
            {"status": "not_found", "user_feedback": "", "target_video_id": "",
             "pushed_to_playlist": False, "source_title": "B"},
            {"status": "uncertain", "user_feedback": "confirmed", "target_video_id": "v3",
             "pushed_to_playlist": False, "source_title": "C"},
        ]
        result = compute_push_plan(tracks)
        assert len(result) == 2
        assert result[0]["source_title"] == "A"
        assert result[1]["source_title"] == "C"

    def test_excludes_already_pushed(self):
        tracks = [
            {"status": "matched", "user_feedback": "", "target_video_id": "v1",
             "pushed_to_playlist": True, "source_title": "A"},
        ]
        result = compute_push_plan(tracks)
        assert result == []

    def test_empty_input_returns_empty(self):
        assert compute_push_plan([]) == []


class TestClassifySyncError:

    def test_spotify_not_allowlisted(self):
        category, msg = classify_sync_error("403 user may not be registered")
        assert category == "spotify_not_allowlisted"
        assert "Spotify" in msg

    def test_spotify_v1_me_403(self):
        category, msg = classify_sync_error("403 error at /v1/me endpoint")
        assert category == "spotify_not_allowlisted"

    def test_token_expired(self):
        category, msg = classify_sync_error("token expired")
        assert category == "token_expired"
        assert "reconnect" in msg.lower()

    def test_rate_limited(self):
        category, msg = classify_sync_error("429 rate limit exceeded")
        assert category == "rate_limited"

    def test_unknown_error(self):
        category, msg = classify_sync_error("something weird happened")
        assert category == "unknown"
