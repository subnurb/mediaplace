"""Library views — cross-platform music library management."""

import json
import logging
import os
import re
import tempfile
import threading
import unicodedata

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from api.models import (
    LibraryEntry,
    LibraryPlaylist,
    SourceConnection,
    SyncTrack,
    TrackSource,
)
from api.views import require_login

logger = logging.getLogger(__name__)

# In-memory sets (per-process)
_fingerprinting_in_progress: set = set()   # TrackSource IDs being fingerprinted
_stop_requested: set = set()               # LibraryPlaylist IDs whose sync should abort


def _norm(s: str) -> str:
    """Base normalization: accents, parentheticals, lowercase, word-chars only."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", "", s)   # strip (feat. X), [Remix], etc.
    s = re.sub(r"[^\w\s]", " ", s)                  # punctuation → space (hyphens too)
    return re.sub(r"\s+", " ", s).strip()


# Suffixes YouTube appends to channel names: "AURORA - Topic", "Vevo", etc.
_YT_SUFFIX_RE = re.compile(
    r'\s*[-–]\s*(?:topic|official|music|vevo|records|tv|channel|hd|4k|'
    r'worldwide|audio|video|lyrics|presents)\s*$',
    re.I,
)

# Pattern for "Artist - Song" in a raw title (before normalization collapses hyphens)
_ARTIST_TITLE_RE = re.compile(r'^(.{2,60}?)\s*[-–]\s*(.{2,}.*)$')


def _norm_artist(artist: str) -> str:
    """Normalize artist name, stripping YouTube channel suffixes (e.g. '- Topic')."""
    if not artist:
        return ""
    artist = _YT_SUFFIX_RE.sub("", artist).strip()
    return _norm(artist)


def _title_candidates(raw_title: str) -> list[str]:
    """Return normalized title variants.

    If the raw title looks like "Artist - Song", also returns just the
    song portion so cross-platform grouping works when only one platform
    embeds the artist in the title.
    """
    full = _norm(raw_title)
    candidates = [full]
    m = _ARTIST_TITLE_RE.match(raw_title.strip())
    if m:
        song_only = _norm(m.group(2).strip())
        if song_only and song_only != full:
            candidates.append(song_only)
    return candidates


# ── Library list ──────────────────────────────────────────────────────────────

@require_login
def library_list(request):
    """GET /api/library/
    Returns a paginated, filtered, sorted list of library tracks.
    Each item represents one unique recording (grouped by AudioFingerprint MBID).
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    user = request.user

    # Collect all LibraryEntry rows for this user
    entries = (
        LibraryEntry.objects
        .filter(library_playlist__user=user)
        .select_related(
            "track_source__fingerprint",
            "library_playlist__source",
        )
    )

    # Build canonical track groups keyed by fingerprint or track_source
    groups = {}  # key → {canonical data, sources set, playlists set}

    for entry in entries:
        ts = entry.track_source
        fp = ts.fingerprint

        # Group priority: MBID → Shazam ID → per-track fallback
        # Use content-based keys (mbid value, shazam_id value) rather than fp.id
        # so tracks with the same MBID/Shazam ID group together even if they have
        # separate AudioFingerprint records (before identity linking has run).
        if fp and fp.mbid:
            group_key = f"mbid:{fp.mbid}"
        elif fp and fp.shazam_id:
            group_key = f"shazam:{fp.shazam_id}"
        else:
            group_key = f"ts:{ts.id}"

        if group_key not in groups:
            # Pick the best title/artist from this track_source (or fp if available)
            groups[group_key] = {
                "canonical_id": group_key,
                "title": ts.title or "",
                "artist": ts.artist or "",
                "duration_ms": ts.duration_ms,
                "artwork_url": ts.artwork_url or "",
                "bpm": fp.bpm if fp else None,
                "key": fp.key if fp else "",
                "mode": fp.mode if fp else "",
                "isrcs": fp.isrcs if fp else [],
                "mbid": fp.mbid if fp else "",
                "shazam_id": fp.shazam_id if fp else "",
                "shazam_genre": fp.shazam_genre if fp else "",
                "shazam_spotify_uri": fp.shazam_spotify_uri if fp else "",
                "shazam_cover_url": fp.shazam_cover_url if fp else "",
                "has_fingerprint": fp is not None,
                "sources": {},   # platform+source_id → {platform, url, source_name}
                "playlists": {},  # lp_id → {id, name, platform}
            }

        grp = groups[group_key]

        # Prefer longer title/artist across sources
        if ts.title and len(ts.title) > len(grp["title"]):
            grp["title"] = ts.title
        if ts.artist and len(ts.artist) > len(grp["artist"]):
            grp["artist"] = ts.artist
        if grp["duration_ms"] is None and ts.duration_ms is not None:
            grp["duration_ms"] = ts.duration_ms
        if not grp["artwork_url"] and ts.artwork_url:
            grp["artwork_url"] = ts.artwork_url

        # Add this platform source
        src_key = f"{ts.platform}:{ts.track_id}"
        if src_key not in grp["sources"]:
            grp["sources"][src_key] = {
                "platform": ts.platform,
                "url": ts.url or "",
                "track_id": ts.track_id,
                "track_source_id": ts.id,
                "fingerprinting": ts.id in _fingerprinting_in_progress,
                "has_url": bool(ts.url),
                "source_name": entry.library_playlist.source.name,
            }

        # Add the playlist this entry belongs to
        lp = entry.library_playlist
        if lp.id not in grp["playlists"]:
            grp["playlists"][lp.id] = {
                "id": lp.id,
                "name": lp.playlist_name,
                "platform": lp.source.source_type,
            }

    # ── Secondary merge pass: title+artist cross-platform grouping ────────────
    # Tracks from different platforms with no shared AudioFingerprint are merged
    # when their titles (and optionally artists) normalize to the same value.
    # Multi-key lookup handles the two common YouTube/SoundCloud mismatches:
    #   1. YouTube artist = "AURORA - Topic"  →  strip suffix → "aurora"
    #   2. YouTube title  = "AURORA - Runaway" →  also try song-only "runaway"
    # Same-platform groups are never merged.

    def _group_keys(grp: dict) -> list[tuple[str, str]]:
        """All (title_key, artist_key) candidates for a group, most-specific first."""
        na = _norm_artist(grp["artist"])
        title_cands = _title_candidates(grp["title"])
        keys: list[tuple[str, str]] = []
        for tc in title_cands:
            if not tc:
                continue
            if na:
                keys.append((tc, na))
        # Title-only secondary key: lets a group with no artist match one with an
        # artist. Also registered for groups WITH an artist so they are discoverable
        # by groups that lack artist info (e.g. some YouTube tracks).
        for tc in title_cands:
            if tc:
                keys.append((tc, ""))
        return keys

    key_index: dict[tuple, str] = {}   # key → canonical group_key
    merged_away: set[str] = set()

    def _absorb(canon_key: str, child_key: str):
        canon = groups[canon_key]
        child = groups[child_key]
        canon["sources"].update(child["sources"])
        canon["playlists"].update(child["playlists"])
        if not canon["artwork_url"] and child["artwork_url"]:
            canon["artwork_url"] = child["artwork_url"]
        if canon["bpm"] is None and child["bpm"] is not None:
            canon["bpm"] = child["bpm"]
        if not canon["key"] and child["key"]:
            canon["key"] = child["key"]
        if not canon["mode"] and child["mode"]:
            canon["mode"] = child["mode"]
        for field in ("shazam_id", "shazam_genre", "shazam_spotify_uri", "shazam_cover_url"):
            if not canon.get(field) and child.get(field):
                canon[field] = child[field]
        merged_away.add(child_key)

    for gk in list(groups.keys()):
        if gk in merged_away:
            continue
        grp = groups[gk]
        if not grp["title"]:
            continue

        keys = _group_keys(grp)
        curr_platforms = {s["platform"] for s in grp["sources"].values()}

        # Check if any key matches a previously registered group
        matched = None
        for k in keys:
            if k in key_index:
                candidate = key_index[k]
                if candidate in merged_away:
                    continue
                canon_platforms = {s["platform"] for s in groups[candidate]["sources"].values()}
                if canon_platforms.isdisjoint(curr_platforms):
                    matched = candidate
                    break

        if matched:
            _absorb(matched, gk)
        else:
            # Register all keys pointing to this group (don't overwrite existing)
            for k in keys:
                if k not in key_index:
                    key_index[k] = gk

    # Remove merged-away groups
    for gk in merged_away:
        del groups[gk]

    results = list(groups.values())

    # Flatten sources/playlists dicts to lists
    for grp in results:
        grp["sources"] = list(grp["sources"].values())
        grp["playlists"] = list(grp["playlists"].values())
        grp["platform_count"] = len(grp["sources"])

    # ── Filters ──────────────────────────────────────────────────────────────
    q = request.GET.get("q", "").strip().lower()
    platform = request.GET.get("platform", "").strip()
    playlist_id = request.GET.get("playlist_id", "").strip()
    bpm_min = request.GET.get("bpm_min", "")
    bpm_max = request.GET.get("bpm_max", "")
    key_filter = request.GET.get("key", "").strip()
    mode_filter = request.GET.get("mode", "").strip()

    if q:
        results = [r for r in results if q in r["title"].lower() or q in r["artist"].lower()]
    if platform:
        results = [r for r in results if any(s["platform"] == platform for s in r["sources"])]
    if playlist_id:
        try:
            pid = int(playlist_id)
            results = [r for r in results if any(p["id"] == pid for p in r["playlists"])]
        except ValueError:
            pass
    if bpm_min:
        try:
            bpm_min_f = float(bpm_min)
            results = [r for r in results if r["bpm"] is not None and r["bpm"] >= bpm_min_f]
        except ValueError:
            pass
    if bpm_max:
        try:
            bpm_max_f = float(bpm_max)
            results = [r for r in results if r["bpm"] is not None and r["bpm"] <= bpm_max_f]
        except ValueError:
            pass
    if key_filter:
        results = [r for r in results if r["key"].lower() == key_filter.lower()]
    if mode_filter:
        results = [r for r in results if r["mode"].lower() == mode_filter.lower()]

    # ── Sort ──────────────────────────────────────────────────────────────────
    sort = request.GET.get("sort", "title").strip()
    reverse = sort.startswith("-")
    sort_key = sort.lstrip("-")

    def _sort_val(r):
        v = r.get(sort_key)
        if v is None:
            return (1, "")  # nulls last
        if isinstance(v, str):
            return (0, v.lower())
        return (0, v)

    results.sort(key=_sort_val, reverse=reverse)

    # ── Pagination ────────────────────────────────────────────────────────────
    try:
        page = max(1, int(request.GET.get("page", 1)))
    except ValueError:
        page = 1
    page_size = 50
    total = len(results)
    start = (page - 1) * page_size
    results = results[start: start + page_size]

    return JsonResponse({
        "results": results,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    })


# ── Library Settings ──────────────────────────────────────────────────────────

@csrf_exempt
@require_login
def library_settings(request):
    """GET/POST /api/library/settings/"""
    user = request.user

    if request.method == "GET":
        playlists = (
            LibraryPlaylist.objects
            .filter(user=user)
            .select_related("source")
            .order_by("created_at")
        )
        return JsonResponse({"playlists": [p.to_dict() for p in playlists]})

    if request.method == "POST":
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        source_id = body.get("source_id")
        playlist_id = body.get("playlist_id", "").strip()
        playlist_name = body.get("playlist_name", "").strip()

        if not source_id or not playlist_id or not playlist_name:
            return JsonResponse({"error": "source_id, playlist_id and playlist_name are required"}, status=400)

        try:
            source = SourceConnection.objects.get(id=source_id, user=user)
        except SourceConnection.DoesNotExist:
            return JsonResponse({"error": "Source not found"}, status=404)

        lp, created = LibraryPlaylist.objects.get_or_create(
            user=user,
            source=source,
            playlist_id=playlist_id,
            defaults={"playlist_name": playlist_name},
        )
        if not created and lp.playlist_name != playlist_name:
            lp.playlist_name = playlist_name
            lp.save(update_fields=["playlist_name"])

        # Mark syncing before returning so the frontend can start polling immediately
        LibraryPlaylist.objects.filter(id=lp.id).update(
            syncing=True, sync_progress=0, sync_phase="importing",
        )
        lp.syncing = True
        lp.sync_progress = 0
        lp.sync_phase = "importing"

        threading.Thread(
            target=_run_library_sync,
            args=(lp.id,),
            daemon=True,
        ).start()

        return JsonResponse(lp.to_dict(), status=201 if created else 200)

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
@require_login
def library_settings_detail(request, playlist_id):
    """DELETE /api/library/settings/<id>/"""
    if request.method != "DELETE":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        lp = LibraryPlaylist.objects.get(id=playlist_id, user=request.user)
    except LibraryPlaylist.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    lp.delete()
    return JsonResponse({"ok": True})


@csrf_exempt
@require_login
def library_settings_sync(request, playlist_id):
    """POST /api/library/settings/<id>/sync/ — Re-sync a tracked playlist."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        lp = LibraryPlaylist.objects.get(id=playlist_id, user=request.user)
    except LibraryPlaylist.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    if lp.syncing:
        return JsonResponse({"error": "Already syncing"}, status=409)

    LibraryPlaylist.objects.filter(id=lp.id).update(
        syncing=True, sync_progress=0, sync_phase="importing",
    )
    lp.syncing = True
    lp.sync_progress = 0
    lp.sync_phase = "importing"

    threading.Thread(
        target=_run_library_sync,
        args=(lp.id,),
        daemon=True,
    ).start()

    return JsonResponse(lp.to_dict())


@csrf_exempt
@require_login
def library_settings_stop(request, playlist_id):
    """POST /api/library/settings/<id>/stop/ — Request a running sync to stop."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        lp = LibraryPlaylist.objects.get(id=playlist_id, user=request.user)
    except LibraryPlaylist.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    if lp.syncing:
        _stop_requested.add(playlist_id)

    return JsonResponse(lp.to_dict())


# ── Per-track fingerprint endpoint ───────────────────────────────────────────

@csrf_exempt
@require_login
def library_fingerprint_track(request, ts_id):
    """POST /api/library/tracks/<ts_id>/fingerprint/
    Triggers AcoustID fingerprinting for a specific TrackSource in the background.
    Returns immediately; client should poll GET /api/library/ for results.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        ts = TrackSource.objects.get(id=ts_id)
    except TrackSource.DoesNotExist:
        return JsonResponse({"error": "Not found"}, status=404)

    # Verify this TrackSource belongs to the user's library
    in_library = LibraryEntry.objects.filter(
        library_playlist__user=request.user,
        track_source=ts,
    ).exists()
    if not in_library:
        return JsonResponse({"error": "Not in your library"}, status=403)

    if not ts.url:
        return JsonResponse({"error": "No audio URL available for this track"}, status=422)

    if ts.id in _fingerprinting_in_progress:
        return JsonResponse({"ok": True, "status": "already_running"})

    threading.Thread(
        target=_run_fingerprint_track,
        args=(ts.id,),
        daemon=True,
    ).start()

    return JsonResponse({"ok": True, "status": "started"})


def _run_fingerprint_track(ts_id: int):
    """Background worker: fingerprint one TrackSource via AcoustID."""
    from django.db import close_old_connections
    from api.sync_views import _get_or_build_fingerprint

    _fingerprinting_in_progress.add(ts_id)
    close_old_connections()
    try:
        ts = TrackSource.objects.get(id=ts_id)
        if not ts.url:
            return
        with tempfile.TemporaryDirectory() as tmp_dir:
            fp = _get_or_build_fingerprint(
                platform=ts.platform,
                track_id=ts.track_id,
                audio_url=ts.url,
                tmp_dir=tmp_dir,
                prefix=f"fp_{ts_id}",
            )
            if fp:
                logger.info("[library_fp] ts=%s → mbid=%s bpm=%s key=%s", ts_id, fp.mbid, fp.bpm, fp.key)
            else:
                logger.warning("[library_fp] ts=%s fingerprinting returned no result", ts_id)
    except Exception as exc:
        logger.error("[library_fp] ts=%s error: %s", ts_id, exc, exc_info=True)
    finally:
        _fingerprinting_in_progress.discard(ts_id)
        close_old_connections()


# ── Analyze-all worker ────────────────────────────────────────────────────────

@csrf_exempt
@require_login
def library_analyze_all(request):
    """POST /api/library/analyze-all/
    Queue fingerprinting for every TrackSource in the user's library that has no
    audio features (bpm null AND key empty).  Returns {"count": N}.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    from django.db.models import Q

    ts_ids = list(
        TrackSource.objects
        .filter(library_entries__library_playlist__user=request.user)
        .exclude(url="")
        .filter(
            Q(fingerprint__isnull=True) |
            Q(fingerprint__bpm__isnull=True, fingerprint__key="")
        )
        .distinct()
        .values_list("id", flat=True)
    )

    if not ts_ids:
        return JsonResponse({"count": 0})

    threading.Thread(target=_run_analyze_all, args=(ts_ids,), daemon=True).start()
    logger.info("[library_analyze_all] queued %d tracks", len(ts_ids))
    return JsonResponse({"count": len(ts_ids)})


def _run_analyze_all(ts_ids: list):
    """Background worker: fingerprint a list of TrackSources sequentially."""
    from django.db import close_old_connections
    from api.sync_views import _get_or_build_fingerprint

    close_old_connections()
    with tempfile.TemporaryDirectory() as tmp_dir:
        for ts_id in ts_ids:
            close_old_connections()
            _fingerprinting_in_progress.add(ts_id)
            try:
                ts = TrackSource.objects.filter(id=ts_id).first()
                if not ts or not ts.url:
                    continue
                fp = _get_or_build_fingerprint(
                    platform=ts.platform,
                    track_id=ts.track_id,
                    audio_url=ts.url,
                    tmp_dir=tmp_dir,
                    prefix=f"all_{ts_id}",
                )
                if fp:
                    logger.info("[analyze_all] ts=%s bpm=%s key=%s", ts_id, fp.bpm, fp.key)
            except Exception as exc:
                logger.warning("[analyze_all] ts=%s error: %s", ts_id, exc)
            finally:
                _fingerprinting_in_progress.discard(ts_id)
    close_old_connections()
    logger.info("[analyze_all] done, processed %d tracks", len(ts_ids))


# ── Background sync worker ────────────────────────────────────────────────────

def _link_by_fingerprint_identity(user_id: int) -> int:
    """Merge AudioFingerprints for library TrackSources that represent the same recording.

    Scans all fingerprinted TrackSources in the user's library and merges their
    AudioFingerprint records when they share:
      1. MBID  (MusicBrainz Recording ID)
      2. Shazam ID
      3. ISRC  (at least one in common)
      4. Local fingerprint Jaccard similarity ≥ 0.15

    Only merges cross-platform pairs (no point merging two SoundCloud tracks).
    Returns the number of merges performed.
    """
    from django.conf import settings
    from api.models import AudioFingerprint, LocalFingerprint  # noqa: F811
    from api.sync_views import _merge_fingerprints

    def _safe_merge(fp_id_a: int, fp_id_b: int) -> int:
        try:
            return _merge_fingerprints(fp_id_a, fp_id_b)
        except Exception as exc:
            logger.warning("[library_sync] fp merge error %s↔%s: %s", fp_id_a, fp_id_b, exc)
            return fp_id_a

    def _load_ts():
        return list(
            TrackSource.objects
            .filter(library_entries__library_playlist__user_id=user_id,
                    fingerprint__isnull=False)
            .select_related("fingerprint")
            .distinct()
        )

    all_ts = _load_ts()
    if not all_ts:
        return 0

    merged = 0

    # ── 1. MBID matching ──────────────────────────────────────────────────────
    mbid_map: dict = {}
    for ts in all_ts:
        if ts.fingerprint and ts.fingerprint.mbid:
            mbid_map.setdefault(ts.fingerprint.mbid, []).append(ts)

    for mbid, ts_list in mbid_map.items():
        fp_ids = list({ts.fingerprint_id for ts in ts_list})
        if len(fp_ids) < 2:
            continue
        if len({ts.platform for ts in ts_list}) < 2:
            continue  # all same platform — skip
        winner_id = fp_ids[0]
        for loser_id in fp_ids[1:]:
            winner_id = _safe_merge(winner_id, loser_id)
            merged += 1
            logger.debug("[library_sync] merged by MBID=%s fp %s←%s", mbid, winner_id, loser_id)

    all_ts = _load_ts()  # refresh after merges

    # ── 2. Shazam ID matching ────────────────────────────────────────────────
    shazam_map: dict = {}
    for ts in all_ts:
        if ts.fingerprint and ts.fingerprint.shazam_id:
            shazam_map.setdefault(ts.fingerprint.shazam_id, []).append(ts)

    for shazam_id, ts_list in shazam_map.items():
        fp_ids = list({ts.fingerprint_id for ts in ts_list})
        if len(fp_ids) < 2:
            continue
        if len({ts.platform for ts in ts_list}) < 2:
            continue
        winner_id = fp_ids[0]
        for loser_id in fp_ids[1:]:
            winner_id = _safe_merge(winner_id, loser_id)
            merged += 1
            logger.debug("[library_sync] merged by Shazam=%s fp %s←%s", shazam_id, winner_id, loser_id)

    all_ts = _load_ts()

    # ── 3. ISRC matching ─────────────────────────────────────────────────────
    isrc_map: dict = {}
    for ts in all_ts:
        for isrc in (ts.fingerprint.isrcs or []) if ts.fingerprint else []:
            isrc_map.setdefault(isrc.strip().upper(), []).append(ts)

    for isrc, ts_list in isrc_map.items():
        fp_ids = list({ts.fingerprint_id for ts in ts_list})
        if len(fp_ids) < 2:
            continue
        if len({ts.platform for ts in ts_list}) < 2:
            continue
        winner_id = fp_ids[0]
        for loser_id in fp_ids[1:]:
            winner_id = _safe_merge(winner_id, loser_id)
            merged += 1
            logger.debug("[library_sync] merged by ISRC=%s fp %s←%s", isrc, winner_id, loser_id)

    # ── 4. Local fingerprint similarity ──────────────────────────────────────
    if getattr(settings, "LOCAL_FINGERPRINT_ENABLED", False):
        all_ts = _load_ts()
        lfp_by_ts_id = {
            lfp.track_source_id: lfp
            for lfp in LocalFingerprint.objects.filter(
                track_source_id__in=[ts.id for ts in all_ts]
            )
        }

        import local_fingerprint_service

        # Group by platform — only compare cross-platform pairs
        by_platform: dict = {}
        for ts in all_ts:
            if ts.id in lfp_by_ts_id:
                by_platform.setdefault(ts.platform, []).append(ts)

        _MAX_PER_PLATFORM = 150  # cap O(n²) comparisons
        platform_keys = list(by_platform.keys())
        for i in range(len(platform_keys)):
            for j in range(i + 1, len(platform_keys)):
                p_a = by_platform[platform_keys[i]][:_MAX_PER_PLATFORM]
                p_b = by_platform[platform_keys[j]][:_MAX_PER_PLATFORM]
                for ts_a in p_a:
                    for ts_b in p_b:
                        if ts_a.fingerprint_id == ts_b.fingerprint_id:
                            continue  # already linked
                        lfp_a = lfp_by_ts_id.get(ts_a.id)
                        lfp_b = lfp_by_ts_id.get(ts_b.id)
                        if not lfp_a or not lfp_b:
                            continue
                        try:
                            sim = local_fingerprint_service.similarity(
                                lfp_a.fingerprint_data, lfp_b.fingerprint_data
                            )
                            if sim >= 0.15:
                                _safe_merge(ts_a.fingerprint_id, ts_b.fingerprint_id)
                                merged += 1
                                logger.debug(
                                    "[library_sync] merged by local FP ts=%s↔ts=%s jaccard=%.3f",
                                    ts_a.id, ts_b.id, sim,
                                )
                        except Exception as exc:
                            logger.debug("[library_sync] local FP sim error: %s", exc)

    if merged:
        logger.info("[library_sync] identity linking: %d merge(s) for user=%s", merged, user_id)
    return merged


def _run_library_sync(library_playlist_id: int):
    """Import tracks from a tracked playlist, then fingerprint new ones."""
    from django.db import close_old_connections

    close_old_connections()

    try:
        lp = LibraryPlaylist.objects.select_related("source", "user").get(id=library_playlist_id)
    except LibraryPlaylist.DoesNotExist:
        return

    logger.info("[library_sync] start playlist=%s (%s)", library_playlist_id, lp.playlist_name)

    def _set_progress(progress: int, phase: str):
        LibraryPlaylist.objects.filter(id=library_playlist_id).update(
            sync_progress=progress, sync_phase=phase,
        )

    def _stopped() -> bool:
        return library_playlist_id in _stop_requested

    try:
        # ── Phase 1: import tracks ────────────────────────────────────────────
        from api.sync_views import _get_tracks_for_source

        raw_tracks = _get_tracks_for_source(lp.source, lp.playlist_id)
        total_tracks = len(raw_tracks)

        # Determine platform key for TrackSource
        platform = lp.source.source_type  # e.g. 'soundcloud', 'youtube_publish'

        current_ts_ids = set()
        last_progress = -1
        for i, track in enumerate(raw_tracks):
            if _stopped():
                logger.info("[library_sync] stopped during import at track %d/%d", i, total_tracks)
                break

            track_id = str(track.get("id") or track.get("track_id") or "")
            if not track_id:
                continue

            track_url = track.get("permalink_url") or track.get("url") or ""
            ts, created = TrackSource.objects.update_or_create(
                platform=platform,
                track_id=track_id,
                defaults={
                    "url": track_url,
                    "title": track.get("title") or "",
                    "artist": track.get("artist") or "",
                    "duration_ms": track.get("duration_ms"),
                    "artwork_url": track.get("artwork_url") or "",
                },
            )
            # Ensure URL is set on pre-existing rows that sync_views left empty
            if not created and track_url and not ts.url:
                TrackSource.objects.filter(id=ts.id).update(url=track_url)
                ts.url = track_url

            entry, _ = LibraryEntry.objects.get_or_create(
                library_playlist=lp,
                track_source=ts,
                defaults={"position": i},
            )
            if entry.position != i:
                LibraryEntry.objects.filter(id=entry.id).update(position=i)

            current_ts_ids.add(ts.id)

            # Update progress 0→50 (import phase), write only when integer changes
            if total_tracks > 0:
                p = int((i + 1) / total_tracks * 50)
                if p != last_progress:
                    _set_progress(p, "importing")
                    last_progress = p

        if _stopped():
            return

        # Remove stale entries (tracks no longer in playlist)
        LibraryEntry.objects.filter(library_playlist=lp).exclude(
            track_source_id__in=current_ts_ids
        ).delete()

        track_count = len(current_ts_ids)
        LibraryPlaylist.objects.filter(id=library_playlist_id).update(track_count=track_count)
        logger.info("[library_sync] imported %d tracks for playlist=%s", track_count, library_playlist_id)

        # ── Phase 1.5: apply confirmed / high-confidence SyncTrack matches ────
        # For each imported TrackSource, look up SyncTrack rows where the user
        # confirmed the match or the auto-match confidence is ≥ 0.85.
        # When a match is found we:
        #   1. Ensure the target TrackSource exists in the DB.
        #   2. Share the same AudioFingerprint record between source and target so
        #      both sides immediately group together in the library (fp.id grouping).
        from django.db.models import Q as _Q

        imported_ts_qs = (
            TrackSource.objects
            .filter(id__in=current_ts_ids)
            .select_related("fingerprint")
        )
        linked = 0
        for ts in imported_ts_qs:
            close_old_connections()
            confirmed_matches = (
                SyncTrack.objects
                .filter(
                    source_track_id=ts.track_id,
                    job__source_from__source_type=ts.platform,
                )
                .filter(
                    _Q(user_feedback="confirmed") |
                    _Q(status="matched", match_confidence__gte=0.85)
                )
                .exclude(target_video_id="")
                .select_related("job__source_to")
            )
            for m in confirmed_matches:
                tgt_type = m.job.source_to.source_type
                tgt_id = m.target_video_id

                if tgt_type == SourceConnection.SourceType.YOUTUBE_PUBLISH:
                    tgt_url = f"https://www.youtube.com/watch?v={tgt_id}"
                else:
                    tgt_url = tgt_id  # SoundCloud stores permalink as track_id

                tgt_ts, _ = TrackSource.objects.get_or_create(
                    platform=tgt_type,
                    track_id=tgt_id,
                    defaults={"url": tgt_url, "title": m.target_title or ""},
                )
                if not tgt_ts.url and tgt_url:
                    TrackSource.objects.filter(id=tgt_ts.id).update(url=tgt_url)

                # Share fingerprint: whichever side already has one, assign to the other
                ts.refresh_from_db(fields=["fingerprint"])
                tgt_ts.refresh_from_db(fields=["fingerprint"])
                if ts.fingerprint_id and not tgt_ts.fingerprint_id:
                    TrackSource.objects.filter(id=tgt_ts.id).update(fingerprint_id=ts.fingerprint_id)
                    linked += 1
                    logger.debug("[library_sync] fp link ts=%s → tgt=%s (conf=%.2f feedback=%s)",
                                 ts.id, tgt_ts.id, m.match_confidence or 0, m.user_feedback)
                elif tgt_ts.fingerprint_id and not ts.fingerprint_id:
                    TrackSource.objects.filter(id=ts.id).update(fingerprint_id=tgt_ts.fingerprint_id)
                    linked += 1
                    logger.debug("[library_sync] fp link tgt=%s → ts=%s (conf=%.2f feedback=%s)",
                                 tgt_ts.id, ts.id, m.match_confidence or 0, m.user_feedback)

        if linked:
            logger.info("[library_sync] linked %d cross-platform pairs via SyncTrack matches", linked)

        # ── Phase 2: fingerprint unanalyzed tracks ────────────────────────────
        from api.sync_views import _get_or_build_fingerprint

        unfingerprinted = list(
            TrackSource.objects
            .filter(
                library_entries__library_playlist=lp,
                fingerprint__isnull=True,
            )
            .exclude(url="")
        )
        total_fp = len(unfingerprinted)
        _set_progress(50, "fingerprinting")

        with tempfile.TemporaryDirectory() as tmp_dir:
            for j, ts in enumerate(unfingerprinted):
                if _stopped():
                    logger.info("[library_sync] stopped during fingerprinting at %d/%d", j, total_fp)
                    break

                close_old_connections()
                try:
                    fp = _get_or_build_fingerprint(
                        platform=ts.platform,
                        track_id=ts.track_id,
                        audio_url=ts.url,
                        tmp_dir=tmp_dir,
                        prefix=f"lib_{ts.id}",
                    )
                    if fp:
                        logger.debug("[library_sync] fingerprinted ts=%s mbid=%s bpm=%s", ts.id, fp.mbid, fp.bpm)
                except Exception as exc:
                    logger.warning("[library_sync] fingerprint failed ts=%s: %s", ts.id, exc)

                # Update progress 50→80 (fingerprint phase)
                if total_fp > 0:
                    p = 50 + int((j + 1) / total_fp * 30)
                    _set_progress(p, "fingerprinting")

        if _stopped():
            return

        # ── Phase 2.5: enrich already-fingerprinted tracks missing Shazam / local FP
        # Runs Shazam (subprocess) and local FP on tracks fingerprinted in a
        # previous sync that didn't have these enrichments yet.  No-ops when
        # data is already present, so this is safe to run every sync.
        from django.conf import settings as _settings
        from api.sync_views import _run_shazam_sync, _run_local_fingerprint_sync

        shazam_on = getattr(_settings, "SHAZAM_ENABLED", False)
        local_fp_on = getattr(_settings, "LOCAL_FINGERPRINT_ENABLED", False)

        if shazam_on or local_fp_on:
            _set_progress(81, "enriching")
            needs_enrich = list(
                TrackSource.objects
                .filter(library_entries__library_playlist=lp, fingerprint__isnull=False)
                .select_related("fingerprint")
                .distinct()
            )
            total_enrich = len(needs_enrich)
            for k, ts in enumerate(needs_enrich):
                if _stopped():
                    break
                close_old_connections()
                fp = ts.fingerprint
                if not fp:
                    continue
                try:
                    if shazam_on and not fp.shazam_id:
                        _run_shazam_sync(fp.id, ts.id)
                        fp.refresh_from_db()
                    if local_fp_on:
                        _run_local_fingerprint_sync(ts.id, None)
                except Exception as exc:
                    logger.warning("[library_sync] enrich error ts=%s: %s", ts.id, exc)
                if total_enrich > 0:
                    p = 81 + int((k + 1) / total_enrich * 9)
                    _set_progress(p, "enriching")

        if _stopped():
            return

        # ── Phase 3: cross-platform identity linking ──────────────────────────
        # Uses MBID / Shazam ID / ISRC / local FP to merge fingerprint records
        # for tracks from different platforms that are the same recording.
        _set_progress(91, "linking")
        try:
            _link_by_fingerprint_identity(lp.user.id)
        except Exception as exc:
            logger.warning("[library_sync] identity linking error: %s", exc)

        _set_progress(100, "done")

    except Exception as exc:
        logger.error("[library_sync] error playlist=%s: %s", library_playlist_id, exc, exc_info=True)
    finally:
        _stop_requested.discard(library_playlist_id)
        close_old_connections()
        LibraryPlaylist.objects.filter(id=library_playlist_id).update(
            syncing=False,
            sync_progress=0,
            sync_phase="",
            last_synced_at=timezone.now(),
        )
        logger.info("[library_sync] done playlist=%s", library_playlist_id)
