import pickle

from django.conf import settings
from django.db import models


class SourceConnection(models.Model):
    """A user's connection to an external source (streaming platform, local disk, FTP, etc.)."""

    class SourceType(models.TextChoices):
        YOUTUBE_PUBLISH = "youtube_publish", "YouTube (Publish)"
        SOUNDCLOUD = "soundcloud", "SoundCloud"
        SPOTIFY = "spotify", "Spotify"
        DEEZER = "deezer", "Deezer"
        LOCAL = "local", "Local Disk"
        FTP = "ftp", "FTP Server"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sources",
    )
    source_type = models.CharField(max_length=50, choices=SourceType.choices)
    name = models.CharField(max_length=100)
    credentials_data = models.BinaryField(null=True, blank=True)
    config = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "source_connections"
        ordering = ["source_type", "name"]

    def to_dict(self):
        return {
            "id": self.id,
            "source_type": self.source_type,
            "name": self.name,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
        }

    def get_credentials(self):
        """Return valid OAuth credentials, refreshing if expired. None if not set/invalid."""
        if not self.credentials_data:
            return None
        from google.auth.transport.requests import Request

        creds = pickle.loads(bytes(self.credentials_data))
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self.credentials_data = pickle.dumps(creds)
                self.save(update_fields=["credentials_data", "updated_at"])
            else:
                return None
        return creds


class PendingJob(models.Model):
    """A video that has been created and is waiting to be published or downloaded."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="jobs",
    )
    source = models.ForeignKey(
        SourceConnection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="jobs",
    )
    video_path = models.CharField(max_length=500)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    tags = models.JSONField(default=list)
    privacy = models.CharField(max_length=20, default="unlisted")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pending_jobs"
        ordering = ["-created_at"]

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "tags": self.tags,
            "privacy": self.privacy,
            "source_id": self.source_id,
        }


class SyncJob(models.Model):
    """A request to sync a playlist from one source to another."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ANALYZING = "analyzing", "Analyzing"
        READY = "ready", "Ready to upload"
        SYNCING = "syncing", "Uploading"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sync_jobs",
    )
    source_from = models.ForeignKey(
        SourceConnection,
        on_delete=models.CASCADE,
        related_name="sync_jobs_from",
    )
    source_to = models.ForeignKey(
        SourceConnection,
        on_delete=models.CASCADE,
        related_name="sync_jobs_to",
    )
    playlist_id = models.CharField(max_length=200)
    playlist_name = models.CharField(max_length=300)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Populated after the user validates and pushes tracks to a target playlist
    target_playlist_id   = models.CharField(max_length=200, blank=True)
    target_playlist_name = models.CharField(max_length=300, blank=True)
    pushed_at            = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "sync_jobs"
        ordering = ["-created_at"]

    def to_dict(self, include_tracks=False):
        data = {
            "id": self.id,
            "source_from": self.source_from.to_dict(),
            "source_to": self.source_to.to_dict(),
            "playlist_id": self.playlist_id,
            "playlist_name": self.playlist_name,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "target_playlist_id": self.target_playlist_id,
            "target_playlist_name": self.target_playlist_name,
            "pushed_at": self.pushed_at.isoformat() if self.pushed_at else None,
        }
        if include_tracks:
            data["tracks"] = [t.to_dict() for t in self.tracks.all()]
        return data


class AudioFingerprint(models.Model):
    """Canonical record for a unique audio recording.

    One row per unique recording, keyed by MBID when resolved via AcoustID.
    Multiple TrackSources from different platforms can link to the same
    AudioFingerprint when they share the same MBID (same recording confirmed).

    algo_version tracks which version of the matching algorithm produced this
    fingerprint. When algo_version < music_matcher.MATCH_ALGO_VERSION the
    fingerprint is stale and will be re-analyzed next time the track is requested.

    source field:
      'acoustid' — MBID resolved via Chromaprint + AcoustID API
      'librosa'  — BPM/key extracted locally (AcoustID DB miss or no API key)
    """

    mbid = models.CharField(max_length=36, blank=True, db_index=True)
    isrcs = models.JSONField(default=list)
    chromaprint = models.TextField(blank=True)          # raw Chromaprint fingerprint string
    bpm = models.FloatField(null=True, blank=True)
    key = models.CharField(max_length=5, blank=True)    # 'C', 'F#', …
    mode = models.CharField(max_length=10, blank=True)  # 'major' | 'minor'
    source = models.CharField(max_length=20, default="acoustid")
    algo_version = models.IntegerField(default=1)
    last_matched_at = models.DateTimeField(null=True, blank=True)
    match_count = models.IntegerField(default=0)

    # ShazamIO recognition fields
    shazam_id = models.CharField(max_length=100, blank=True, db_index=True)
    shazam_title = models.CharField(max_length=400, blank=True)
    shazam_artist = models.CharField(max_length=200, blank=True)
    shazam_album = models.CharField(max_length=300, blank=True)
    shazam_genre = models.CharField(max_length=100, blank=True)
    shazam_spotify_uri = models.CharField(max_length=200, blank=True)
    shazam_cover_url = models.URLField(max_length=500, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "audio_fingerprints"

    def is_stale(self) -> bool:
        """True if this fingerprint was produced by an older algorithm version."""
        from music_matcher import MATCH_ALGO_VERSION
        return self.algo_version < MATCH_ALGO_VERSION

    def audio_features(self) -> dict:
        """Return a dict compatible with music_matcher.analyze_audio_features()."""
        result = {}
        if self.bpm is not None:
            result["tempo"] = self.bpm
        if self.key:
            result["key"] = self.key
        if self.mode:
            result["mode"] = self.mode
        return result


class TrackSource(models.Model):
    """One platform track, optionally linked to an AudioFingerprint.

    Created for every track encountered during search/match — source playlist
    tracks, matched candidates, and upload targets — building a cross-platform
    knowledge base over time.

    The same song on YouTube and SoundCloud will have separate TrackSource rows
    both pointing to the same AudioFingerprint (shared MBID is the bridge).

    platform values: 'soundcloud', 'youtube_publish', …
    track_id: platform-specific ID (YouTube video ID, SoundCloud numeric ID,
              or permalink URL when no numeric ID is available).
    """

    fingerprint = models.ForeignKey(
        AudioFingerprint,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sources",
    )
    platform = models.CharField(max_length=20)
    track_id = models.CharField(max_length=500)
    url = models.URLField(max_length=500, blank=True)
    title = models.CharField(max_length=400, blank=True)
    artist = models.CharField(max_length=200, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    artwork_url = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "track_sources"
        unique_together = [("platform", "track_id")]


class SyncTrack(models.Model):
    """One track within a SyncJob, with its match result and upload status."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        MATCHED = "matched", "Matched"        # already exists on target
        UNCERTAIN = "uncertain", "Uncertain"  # possible match, needs review
        NOT_FOUND = "not_found", "Not found"  # needs upload
        UPLOADING = "uploading", "Uploading"
        UPLOADED = "uploaded", "Uploaded"
        SKIPPED = "skipped", "Skipped"
        FAILED = "failed", "Failed"

    job = models.ForeignKey(SyncJob, on_delete=models.CASCADE, related_name="tracks")

    # Source track metadata (from SoundCloud, etc.)
    source_track_id = models.CharField(max_length=200)
    source_title = models.CharField(max_length=400)
    source_artist = models.CharField(max_length=200, blank=True)
    source_duration_ms = models.IntegerField(null=True, blank=True)
    source_artwork_url = models.URLField(max_length=500, blank=True)
    source_permalink_url = models.URLField(max_length=500, blank=True)

    # Match result (populated after analysis)
    match_confidence = models.FloatField(null=True, blank=True)
    target_video_id = models.CharField(max_length=500, blank=True)  # YouTube video ID or SoundCloud permalink URL
    target_title = models.CharField(max_length=400, blank=True)     # matched video title

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    error = models.TextField(blank=True)
    position = models.IntegerField(default=0)  # track order in playlist

    # User feedback on the algorithmic match
    user_feedback = models.CharField(max_length=10, blank=True)  # 'confirmed' | 'rejected' | ''
    # IDs the user has already rejected (to skip on next search)
    rejected_target_ids = models.JSONField(default=list)
    # Ranked alternative candidates from the initial search (used when user rejects)
    alternatives = models.JSONField(default=list)  # [{video_id, title, artist, confidence}, ...]

    # True after this track has been successfully added to the target playlist via sync_push
    pushed_to_playlist = models.BooleanField(default=False)

    class Meta:
        db_table = "sync_tracks"
        ordering = ["position"]

    def to_dict(self):
        data = {
            "id": self.id,
            "source_track_id": self.source_track_id,
            "source_title": self.source_title,
            "source_artist": self.source_artist,
            "source_duration_ms": self.source_duration_ms,
            "source_artwork_url": self.source_artwork_url,
            "source_permalink_url": self.source_permalink_url,
            "match_confidence": self.match_confidence,
            "target_video_id": self.target_video_id,
            "target_title": self.target_title,
            "status": self.status,
            "error": self.error,
            "user_feedback": self.user_feedback,
            "has_alternatives": bool(self.alternatives),
            "pushed_to_playlist": self.pushed_to_playlist,
        }
        # For not_found tracks send the full candidates list so the frontend
        # can render a search-result picker for manual selection.
        if self.status == self.Status.NOT_FOUND and self.alternatives:
            data["search_results"] = self.alternatives
        return data


class LibraryPlaylist(models.Model):
    """A user-selected playlist to track in the Library."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="library_playlists",
    )
    source = models.ForeignKey(
        SourceConnection,
        on_delete=models.CASCADE,
        related_name="library_playlists",
    )
    playlist_id = models.CharField(max_length=200)
    playlist_name = models.CharField(max_length=300)
    track_count = models.IntegerField(default=0)
    syncing = models.BooleanField(default=False)
    sync_progress = models.IntegerField(default=0)   # 0-100 while syncing
    sync_phase = models.CharField(max_length=50, blank=True, default="")  # "importing" | "fingerprinting"
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "library_playlists"
        unique_together = [("user", "source", "playlist_id")]

    def to_dict(self):
        return {
            "id": self.id,
            "source": self.source.to_dict(),
            "playlist_id": self.playlist_id,
            "playlist_name": self.playlist_name,
            "track_count": self.track_count,
            "syncing": self.syncing,
            "sync_progress": self.sync_progress,
            "sync_phase": self.sync_phase,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
            "created_at": self.created_at.isoformat(),
        }


class CachedAudio(models.Model):
    """Full-quality audio file cached on disk for a TrackSource.

    Populated the first time a track needs its audio (fingerprinting, upload, etc.).
    Subsequent operations reuse the file instead of re-downloading.
    """

    track_source = models.OneToOneField(
        TrackSource,
        on_delete=models.CASCADE,
        related_name="cached_audio",
    )
    file_path = models.CharField(max_length=500)
    file_format = models.CharField(max_length=20, blank=True)   # 'mp3', 'm4a', …
    file_size = models.BigIntegerField(null=True, blank=True)    # bytes
    quality = models.CharField(max_length=50, blank=True, default="best")
    downloaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cached_audio"


class LibraryEntry(models.Model):
    """One track from a tracked playlist, linking a LibraryPlaylist to a TrackSource."""

    library_playlist = models.ForeignKey(
        LibraryPlaylist,
        on_delete=models.CASCADE,
        related_name="entries",
    )
    track_source = models.ForeignKey(
        TrackSource,
        on_delete=models.CASCADE,
        related_name="library_entries",
    )
    position = models.IntegerField(default=0)

    class Meta:
        db_table = "library_entries"
        unique_together = [("library_playlist", "track_source")]
        ordering = ["position"]


class LocalFingerprint(models.Model):
    """Dejavu-inspired local audio fingerprint stored per TrackSource.

    Independent of AcoustID: computed entirely offline from the audio file
    using spectrogram peak constellations (the same algorithm Dejavu uses).
    Stored in its own table so it never contaminates the main AudioFingerprint
    record and can be rebuilt independently.

    fingerprint_hash  — SHA-256 of the sorted peak-hash set; unique per recording.
    fingerprint_data  — List of up to 500 short hashes (peak constellation pairs).
                       Used for Jaccard-similarity comparison between two tracks.
    """

    track_source = models.OneToOneField(
        TrackSource,
        on_delete=models.CASCADE,
        related_name="local_fingerprint",
    )
    fingerprint_hash = models.CharField(max_length=64, blank=True, db_index=True)
    fingerprint_data = models.JSONField(default=list)
    duration_s = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "local_fingerprints"


class UserProfile(models.Model):
    """Extended user profile — holds social login IDs."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    google_id = models.CharField(max_length=128, unique=True, null=True, blank=True)

    class Meta:
        db_table = "user_profiles"
