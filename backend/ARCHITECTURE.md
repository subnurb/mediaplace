### Overview

MediaPlace backend follows Domain-Driven Design (DDD) with three core layers: **Domain**, **Application**, and **Infrastructure**, plus an **Interface** layer (Django views/URLs). This structure was introduced incrementally — existing root-level modules remain for backward compatibility while new code follows the layered import paths.

---

### Directory structure

```text
backend/
  api/                            # Interface layer (Django app)
    views.py                      #   HTTP endpoints — auth, sources, jobs
    sync_views.py                 #   HTTP endpoints + orchestration for one-shot playlist sync
    library_views.py              #   HTTP endpoints + orchestration for library management
    urls.py                       #   URL routing
    models.py                     #   Django ORM models (domain entities)
    management/commands/           #   CLI entrypoints (cron, dev server)

  domain/                         # Domain layer — pure business logic, no I/O
    sync/
      services.py                 #   is_track_pushable, compute_push_plan, classify_sync_error
    matching/
      services.py                 #   Facade for music_matcher pure functions (normalize_title, score_candidate, etc.)
    library/
      services.py                 #   norm_text, norm_artist, title_candidates, group_key_variants, should_merge_groups

  application/                    # Application layer — use-case orchestrators

  infrastructure/                 # Infrastructure layer — external system adapters
    platforms/
      spotify.py                  #   Facade → spotify_service (get_playlists, add_tracks_to_playlist, ...)
      soundcloud.py               #   Facade → soundcloud_service
      youtube.py                  #   Facade → youtube_service
    auth/                         #   Facade namespace for auth modules
    audio/                        #   Facade namespace for audio/media modules

  # Root-level modules (backward-compatible, canonical implementations)
  spotify_service.py              #   Spotify Web API adapter (Spotipy)
  soundcloud_service.py           #   SoundCloud API adapter
  youtube_service.py              #   YouTube Data API adapter
  spotify_auth.py                 #   Spotify OAuth 2.0 PKCE
  soundcloud_auth.py              #   SoundCloud OAuth 2.1 PKCE
  google_auth.py                  #   Google OAuth2 sign-in
  music_matcher.py                #   Cross-platform track matching engine
  video_creator.py                #   FFmpeg-based video generation
  youtube_uploader.py             #   YouTube upload via google-api-python-client
  url_downloader.py               #   yt-dlp audio/artwork downloader

  tests/                          # Automated tests (pytest + pytest-django)
    domain/
      test_sync_services.py       #   15 tests for sync error classification & push planning
      test_library_services.py    #   24 tests for library normalization & grouping
    application/                  #   (future: orchestration tests with mocked infra)
    infrastructure/               #   (future: contract tests for platform APIs)

  config/                         #   Django project settings
  pytest.ini                      #   pytest configuration
```

---

### Bounded contexts

| Context | Domain entities | Domain services | Application services | Infrastructure |
|---|---|---|---|---|
| **Sources & Auth** | `SourceConnection`, `UserProfile` | — | — | `spotify_auth`, `soundcloud_auth`, `google_auth`, `youtube_uploader` |
| **Sync** | `SyncJob`, `SyncTrack` | `domain.sync.services` | `api.sync_views` | `spotify_service`, `soundcloud_service`, `youtube_service`, `music_matcher` |
| **Library** | `AudioFingerprint`, `TrackSource`, `LibraryPlaylist`, `LibraryEntry`, `LocalFingerprint` | `domain.library.services` | `api.library_views` | `acoustid_service`, `shazam_service`, `local_fingerprint_service` |
| **Publishing** | `PendingJob` | — | `api.views` (job endpoints) | `video_creator`, `youtube_uploader` |

---

### Layer rules

1. **Domain** (`domain/`) has **no dependencies** on Django ORM, HTTP, or external APIs. Functions take and return plain Python data (dicts, strings, lists). This makes them trivially testable.

2. **Application** (`application/`) coordinates domain services with infrastructure. It may use Django ORM for persistence and call infrastructure adapters for platform API calls. One use-case per function.

3. **Infrastructure** (`infrastructure/`) wraps external systems. The `infrastructure/platforms/` facades re-export from root-level service modules, providing a clean import namespace for new code. Root-level modules remain canonical during the incremental migration.

4. **Interface** (`api/views.py`, `api/urls.py`) handles HTTP request/response translation. Views should delegate to application services for complex workflows and use domain services for business rule checks.

**Import direction**: Interface → Application → Domain ← Infrastructure. Domain never imports from Application or Interface.

---

### How existing code integrates

- `api/sync_views.py` uses `domain.sync.services.classify_sync_error` for structured error mapping in `_run_push`.
- `api/library_views.py` uses `domain.library.services` for `norm_text`, `norm_artist`, `title_candidates`, `group_key_variants`, `should_merge_groups`, and `pick_best_field` — replacing inline implementations.

---

### Testing

See `TESTING.md` for the full testing strategy. Current test suite:

```bash
cd backend && source .venv/bin/activate && pytest tests/domain/ -v
# ~39 tests, ~1 second, no DB or network needed
```

Test organization mirrors DDD layers:
- `tests/domain/` — fast, pure Python, no Django required
- `tests/application/` — Django DB, mocked infrastructure
- `tests/infrastructure/` — contract tests with recorded responses

---

### Migration path (incremental)

The DDD structure is designed for gradual adoption:

1. **Done**: Domain services extracted and tested for sync, library, and matching.
2. **Done**: Infrastructure facades providing clean import paths.
3. **Next**: Extract sync_views workflow orchestration into `application/sync_workflow.py`.
4. **Next**: Extract library sync orchestration into `application/library_sync.py`.
5. **Future**: Move root-level service files into `infrastructure/` directories as canonical locations (one module at a time, updating all imports).
6. **Future**: Introduce DTOs at API boundaries instead of model `to_dict()`.
7. **Future**: Centralize error mapping from all platform exceptions into domain error types.

Each step keeps the system working — run `pytest` and `python manage.py check` to verify.
