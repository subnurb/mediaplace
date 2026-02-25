import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  analyzeAllTracks,
  fetchLibrary,
  fetchLibrarySettings,
  fingerprintTrack,
  setLibraryFilters,
  setLibraryPage,
} from '../store/librarySlice'
import { setActiveTool } from '../store/uiSlice'

// ── Helpers ───────────────────────────────────────────────────────────────────

const SOURCE_META = {
  youtube_publish: { label: 'YT',  icon: 'bi-youtube',   color: 'text-danger',  bg: 'bg-danger-subtle border-danger-subtle'  },
  soundcloud:      { label: 'SC',  icon: 'bi-soundwave',  color: 'text-warning', bg: 'bg-warning-subtle border-warning-subtle' },
  spotify:         { label: 'SP',  icon: 'bi-music-note-beamed', color: 'text-success', bg: 'bg-success-subtle border-success-subtle' },
  deezer:          { label: 'DZ',  icon: 'bi-music-player',      color: 'text-primary', bg: 'bg-primary-subtle border-primary-subtle' },
}

function sourceMeta(platform) {
  return SOURCE_META[platform] || { label: platform, icon: 'bi-plug', color: 'text-muted', bg: 'bg-light border-secondary' }
}

function fmtDuration(ms) {
  if (!ms) return '—'
  const s = Math.round(ms / 1000)
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m}:${sec.toString().padStart(2, '0')}`
}

const KEY_OPTIONS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B',
                     'Cm', 'C#m', 'Dm', 'D#m', 'Em', 'Fm', 'F#m', 'Gm', 'G#m', 'Am', 'A#m', 'Bm']

const PLATFORM_OPTIONS = [
  { value: '', label: 'All Platforms' },
  { value: 'soundcloud', label: 'SoundCloud' },
  { value: 'youtube_publish', label: 'YouTube' },
  { value: 'spotify', label: 'Spotify' },
  { value: 'deezer', label: 'Deezer' },
]

const SORT_OPTIONS = [
  { value: 'title',          label: 'Title A→Z' },
  { value: '-title',         label: 'Title Z→A' },
  { value: 'artist',         label: 'Artist A→Z' },
  { value: '-artist',        label: 'Artist Z→A' },
  { value: 'duration_ms',    label: 'Duration ↑' },
  { value: '-duration_ms',   label: 'Duration ↓' },
  { value: 'bpm',            label: 'BPM ↑' },
  { value: '-bpm',           label: 'BPM ↓' },
  { value: '-platform_count',label: 'Most Platforms' },
]

// ── Platform badge (clickable link) ──────────────────────────────────────────

function PlatformBadge({ source }) {
  const meta = sourceMeta(source.platform)
  const badge = (
    <span
      className={`badge rounded-pill border ${meta.bg} ${meta.color} me-1`}
      style={{ fontSize: '0.7rem' }}
      title={source.url || meta.label}
    >
      <i className={`bi ${meta.icon}`}></i>
      <span className="ms-1">{meta.label}</span>
    </span>
  )
  if (source.url) {
    return (
      <a href={source.url} target="_blank" rel="noreferrer" className="text-decoration-none">
        {badge}
      </a>
    )
  }
  return badge
}

// ── Track row ─────────────────────────────────────────────────────────────────

function TrackRow({ track, analyzing, analyzeAllRunning, onAnalyze }) {
  // No audio features = missing BPM and key (fingerprint may exist but AcousticBrainz was dead)
  const needsAnalysis = !track.bpm && !track.key
  // Spinner when: explicitly triggered, backend flag set, or analyze-all running on this track
  const isFingerprinting = analyzing ||
    track.sources.some(s => s.fingerprinting) ||
    (analyzeAllRunning && needsAnalysis)
  const canAnalyze = needsAnalysis && track.sources.some(s => s.has_url)

  return (
    <tr>
      <td className="py-2 pe-2" style={{ width: 44 }}>
        {track.artwork_url
          ? <img src={track.artwork_url} alt="" width="36" height="36" className="rounded" style={{ objectFit: 'cover' }} />
          : <div className="bg-secondary rounded d-flex align-items-center justify-content-center" style={{ width: 36, height: 36 }}>
              <i className="bi bi-music-note text-white" style={{ fontSize: '1rem' }}></i>
            </div>
        }
      </td>
      <td className="py-2">
        <div className="fw-semibold text-truncate" style={{ maxWidth: 260 }}>{track.title || '—'}</div>
        <div className="text-muted small text-truncate" style={{ maxWidth: 260 }}>{track.artist || '—'}</div>
      </td>
      <td className="py-2 text-muted small text-end">{fmtDuration(track.duration_ms)}</td>
      <td className="py-2 text-center" style={{ minWidth: 72 }}>
        {track.bpm ? (
          <span className="fw-semibold">{Math.round(track.bpm)}</span>
        ) : isFingerprinting ? (
          <span className="spinner-border spinner-border-sm text-primary" role="status" title="Analyzing…"></span>
        ) : canAnalyze ? (
          <button
            className="btn btn-outline-primary btn-sm py-0 px-1"
            style={{ fontSize: '0.65rem' }}
            onClick={() => onAnalyze(track)}
            title="Analyze BPM & key via AcoustID"
          >
            Analyze
          </button>
        ) : (
          <span className="text-muted">—</span>
        )}
      </td>
      <td className="py-2 text-center">
        {track.key
          ? <span className="badge bg-secondary-subtle text-secondary border border-secondary-subtle" style={{ fontSize: '0.72rem' }}>
              {track.key}{track.mode === 'minor' ? 'm' : ''}
            </span>
          : <span className="text-muted">—</span>
        }
      </td>
      <td className="py-2">
        {track.sources.map(s => <PlatformBadge key={`${s.platform}:${s.track_id}`} source={s} />)}
      </td>
      <td className="py-2 text-muted small">
        {track.playlists.slice(0, 2).map(pl => (
          <span key={pl.id} className="d-block text-truncate" style={{ maxWidth: 140 }} title={pl.name}>
            {pl.name}
          </span>
        ))}
        {track.playlists.length > 2 && (
          <span className="text-muted">+{track.playlists.length - 2} more</span>
        )}
      </td>
    </tr>
  )
}

// ── Sort header ───────────────────────────────────────────────────────────────

function SortHeader({ label, field, currentSort, onSort }) {
  const isActive = currentSort === field || currentSort === `-${field}`
  const isDesc = currentSort === `-${field}`
  return (
    <th
      className={`py-2 user-select-none ${isActive ? 'text-primary' : 'text-muted'}`}
      style={{ cursor: 'pointer', fontWeight: 500, fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}
      onClick={() => onSort(field)}
    >
      {label}
      {isActive && (
        <i className={`bi ms-1 ${isDesc ? 'bi-chevron-down' : 'bi-chevron-up'}`} style={{ fontSize: '0.7rem' }}></i>
      )}
    </th>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function LibraryPage() {
  const dispatch = useDispatch()
  const { tracks, total, page, pages, loading, filters, trackedPlaylists } = useSelector(s => s.library)

  const [showFilters, setShowFilters] = useState(false)
  // Set of canonical_ids currently being fingerprinted; '__analyze_all__' is a
  // special marker that keeps the poll alive while analyze-all is running.
  const [analyzingIds, setAnalyzingIds] = useState(new Set())
  const [analyzeAllCount, setAnalyzeAllCount] = useState(0)
  const pollRef = useRef(null)
  const fpPollRef = useRef(null)

  // Set active tool for layout highlighting
  useEffect(() => {
    dispatch(setActiveTool('library'))
    dispatch(fetchLibrarySettings())
  }, [dispatch])

  // Load library whenever page or filters change
  useEffect(() => {
    dispatch(fetchLibrary({ page, filters }))
  }, [dispatch, page, filters])

  // Poll settings while any playlist is syncing, reload library when done
  const wasSyncing = useRef(false)
  useEffect(() => {
    const anySyncing = trackedPlaylists.some(p => p.syncing)

    if (anySyncing && !pollRef.current) {
      pollRef.current = setInterval(async () => {
        const result = await dispatch(fetchLibrarySettings())
        const stillSyncing = result.payload?.some(p => p.syncing)
        if (!stillSyncing && wasSyncing.current) {
          dispatch(fetchLibrary({ page, filters }))
        }
        wasSyncing.current = stillSyncing
        if (!stillSyncing) {
          clearInterval(pollRef.current)
          pollRef.current = null
        }
      }, 3000)
    }

    if (!anySyncing && pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }

    wasSyncing.current = anySyncing
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
  }, [trackedPlaylists, dispatch, page, filters])

  // Poll library while any track is being fingerprinted (or analyze-all is running)
  useEffect(() => {
    if (analyzingIds.size > 0 && !fpPollRef.current) {
      fpPollRef.current = setInterval(async () => {
        const result = await dispatch(fetchLibrary({ page, filters }))
        if (result.payload?.results) {
          const results = result.payload.results
          // Tracks that now have audio features
          const nowAnalyzed = new Set(
            results.filter(t => t.bpm !== null || t.key).map(t => t.canonical_id)
          )
          // Tracks still missing features (relevant for __analyze_all__ removal)
          const stillPending = results.filter(
            t => !t.bpm && !t.key && t.sources.some(s => s.has_url)
          )
          setAnalyzingIds(prev => {
            const next = new Set([...prev].filter(id => !nowAnalyzed.has(id)))
            // Remove analyze-all marker once no visible tracks still need analysis
            if (next.has('__analyze_all__') && stillPending.length === 0) {
              next.delete('__analyze_all__')
              setAnalyzeAllCount(0)
            }
            if (next.size === 0) {
              clearInterval(fpPollRef.current)
              fpPollRef.current = null
            }
            return next
          })
        }
      }, 4000)
    }

    if (analyzingIds.size === 0 && fpPollRef.current) {
      clearInterval(fpPollRef.current)
      fpPollRef.current = null
    }

    return () => {
      if (fpPollRef.current) {
        clearInterval(fpPollRef.current)
        fpPollRef.current = null
      }
    }
  }, [analyzingIds, dispatch, page, filters])

  // ── Analyze handler ───────────────────────────────────────────────────────

  const handleAnalyzeAll = useCallback(async () => {
    const result = await dispatch(analyzeAllTracks())
    const count = result.payload?.count ?? 0
    if (count > 0) {
      setAnalyzeAllCount(count)
      setAnalyzingIds(prev => new Set([...prev, '__analyze_all__']))
    }
  }, [dispatch])

  const handleAnalyze = useCallback(async (track) => {
    // Fingerprint all sources that have a URL (run in parallel)
    const sourcesToFingerprint = track.sources.filter(s => s.has_url && s.track_source_id)
    if (sourcesToFingerprint.length === 0) return

    setAnalyzingIds(prev => new Set([...prev, track.canonical_id]))

    await Promise.allSettled(
      sourcesToFingerprint.map(s => dispatch(fingerprintTrack(s.track_source_id)))
    )
  }, [dispatch])

  // ── Filter handlers ──────────────────────────────────────────────────────

  const handleSearch = useCallback(e => {
    dispatch(setLibraryFilters({ q: e.target.value }))
  }, [dispatch])

  const handleFilterChange = useCallback((key, value) => {
    dispatch(setLibraryFilters({ [key]: value }))
  }, [dispatch])

  const handleSort = useCallback(field => {
    const currentSort = filters.sort
    const newSort = currentSort === field ? `-${field}` : field
    dispatch(setLibraryFilters({ sort: newSort }))
  }, [dispatch, filters.sort])

  const handlePage = useCallback(p => {
    dispatch(setLibraryPage(p))
  }, [dispatch])

  const hasFilters = filters.platform || filters.playlist_id || filters.bpm_min ||
                     filters.bpm_max || filters.key || filters.mode

  // ── Empty state ──────────────────────────────────────────────────────────

  if (!loading && trackedPlaylists.length === 0) {
    return (
      <div className="container-fluid py-4">
        <div className="text-center py-5">
          <i className="bi bi-music-note-list display-1 text-muted mb-3 d-block"></i>
          <h4 className="text-muted">Your library is empty</h4>
          <p className="text-muted mb-4">Add playlists from your connected accounts to build your cross-platform music library.</p>
          <button className="btn btn-primary" onClick={() => dispatch(setActiveTool('library-settings'))}>
            <i className="bi bi-gear me-2"></i>Library Settings
          </button>
        </div>
      </div>
    )
  }

  const startItem = (page - 1) * 50 + 1
  const endItem = Math.min(page * 50, total)

  return (
    <div className="container-fluid py-3">

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="d-flex align-items-center justify-content-between mb-3 flex-wrap gap-2">
        <div>
          <h5 className="mb-0 fw-semibold">Library</h5>
          {total > 0 && !loading && (
            <small className="text-muted">{total} unique {total === 1 ? 'track' : 'tracks'}</small>
          )}
        </div>
        <div className="d-flex gap-2 align-items-center flex-wrap">
          {trackedPlaylists.some(p => p.syncing) && (
            <span className="badge bg-info text-dark d-flex align-items-center gap-1">
              <span className="spinner-border spinner-border-sm" role="status"></span>
              Syncing…
            </span>
          )}
          {analyzingIds.has('__analyze_all__') ? (
            <span className="badge bg-primary-subtle text-primary border border-primary-subtle d-flex align-items-center gap-1">
              <span className="spinner-border spinner-border-sm" role="status"></span>
              Analyzing {analyzeAllCount} tracks…
            </span>
          ) : (
            <button
              className="btn btn-sm btn-outline-primary"
              onClick={handleAnalyzeAll}
              title="Analyze BPM & key for all unanalyzed tracks"
            >
              <i className="bi bi-activity me-1"></i>Analyze All
            </button>
          )}
          <button
            className="btn btn-sm btn-outline-secondary"
            onClick={() => dispatch(setActiveTool('library-settings'))}
          >
            <i className="bi bi-gear me-1"></i>Settings
          </button>
        </div>
      </div>

      {/* ── Search + filter bar ─────────────────────────────────────────── */}
      <div className="card mb-3 border-0 shadow-sm">
        <div className="card-body py-2 px-3">
          <div className="d-flex flex-wrap gap-2 align-items-center">
            {/* Search */}
            <div className="position-relative flex-grow-1" style={{ minWidth: 200 }}>
              <i className="bi bi-search position-absolute text-muted" style={{ left: 10, top: '50%', transform: 'translateY(-50%)', fontSize: '0.85rem' }}></i>
              <input
                type="text"
                className="form-control form-control-sm ps-4"
                placeholder="Search title or artist…"
                value={filters.q}
                onChange={handleSearch}
              />
            </div>

            {/* Platform filter */}
            <select
              className="form-select form-select-sm"
              style={{ width: 'auto' }}
              value={filters.platform}
              onChange={e => handleFilterChange('platform', e.target.value)}
            >
              {PLATFORM_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>

            {/* Sort */}
            <select
              className="form-select form-select-sm"
              style={{ width: 'auto' }}
              value={filters.sort}
              onChange={e => handleFilterChange('sort', e.target.value)}
            >
              {SORT_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>

            {/* More filters toggle */}
            <button
              className={`btn btn-sm ${showFilters || hasFilters ? 'btn-primary' : 'btn-outline-secondary'}`}
              onClick={() => setShowFilters(v => !v)}
            >
              <i className="bi bi-sliders me-1"></i>Filters
              {hasFilters && <span className="badge bg-white text-primary ms-1" style={{ fontSize: '0.65rem' }}>●</span>}
            </button>
          </div>

          {/* Expanded filter panel */}
          {showFilters && (
            <div className="d-flex flex-wrap gap-3 mt-2 pt-2 border-top">
              {/* Playlist filter */}
              <div>
                <label className="form-label small text-muted mb-1">Playlist</label>
                <select
                  className="form-select form-select-sm"
                  value={filters.playlist_id}
                  onChange={e => handleFilterChange('playlist_id', e.target.value)}
                  style={{ minWidth: 160 }}
                >
                  <option value="">All Playlists</option>
                  {trackedPlaylists.map(p => (
                    <option key={p.id} value={p.id}>{p.playlist_name}</option>
                  ))}
                </select>
              </div>

              {/* BPM range */}
              <div>
                <label className="form-label small text-muted mb-1">BPM</label>
                <div className="d-flex align-items-center gap-1">
                  <input
                    type="number"
                    className="form-control form-control-sm"
                    placeholder="Min"
                    value={filters.bpm_min}
                    onChange={e => handleFilterChange('bpm_min', e.target.value)}
                    style={{ width: 70 }}
                  />
                  <span className="text-muted">–</span>
                  <input
                    type="number"
                    className="form-control form-control-sm"
                    placeholder="Max"
                    value={filters.bpm_max}
                    onChange={e => handleFilterChange('bpm_max', e.target.value)}
                    style={{ width: 70 }}
                  />
                </div>
              </div>

              {/* Key filter */}
              <div>
                <label className="form-label small text-muted mb-1">Key</label>
                <select
                  className="form-select form-select-sm"
                  value={filters.key}
                  onChange={e => handleFilterChange('key', e.target.value)}
                  style={{ minWidth: 90 }}
                >
                  <option value="">Any</option>
                  {KEY_OPTIONS.map(k => <option key={k} value={k}>{k}</option>)}
                </select>
              </div>

              {/* Mode filter */}
              <div>
                <label className="form-label small text-muted mb-1">Mode</label>
                <div className="btn-group btn-group-sm">
                  {['', 'major', 'minor'].map(m => (
                    <button
                      key={m}
                      type="button"
                      className={`btn btn-outline-secondary ${filters.mode === m ? 'active' : ''}`}
                      onClick={() => handleFilterChange('mode', m)}
                    >
                      {m === '' ? 'All' : m.charAt(0).toUpperCase() + m.slice(1)}
                    </button>
                  ))}
                </div>
              </div>

              {/* Clear filters */}
              {hasFilters && (
                <div className="d-flex align-items-end">
                  <button
                    className="btn btn-sm btn-outline-danger"
                    onClick={() => dispatch(setLibraryFilters({
                      platform: '', playlist_id: '', bpm_min: '', bpm_max: '', key: '', mode: ''
                    }))}
                  >
                    <i className="bi bi-x-circle me-1"></i>Clear
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── Track table ─────────────────────────────────────────────────── */}
      {loading ? (
        <div className="text-center py-5">
          <div className="spinner-border text-primary" role="status"></div>
          <div className="mt-2 text-muted small">Loading library…</div>
        </div>
      ) : tracks.length === 0 ? (
        <div className="text-center py-5 text-muted">
          <i className="bi bi-search display-4 mb-3 d-block"></i>
          <p>No tracks match your filters.</p>
          {hasFilters && (
            <button
              className="btn btn-sm btn-outline-secondary"
              onClick={() => dispatch(setLibraryFilters({
                q: '', platform: '', playlist_id: '', bpm_min: '', bpm_max: '', key: '', mode: ''
              }))}
            >
              Clear all filters
            </button>
          )}
        </div>
      ) : (
        <>
          <div className="card border-0 shadow-sm overflow-hidden">
            <div className="table-responsive">
              <table className="table table-hover mb-0 align-middle">
                <thead className="bg-light border-bottom">
                  <tr>
                    <th style={{ width: 44 }}></th>
                    <SortHeader label="Title / Artist" field="title" currentSort={filters.sort} onSort={handleSort} />
                    <SortHeader label="Dur" field="duration_ms" currentSort={filters.sort} onSort={handleSort} />
                    <SortHeader label="BPM" field="bpm" currentSort={filters.sort} onSort={handleSort} />
                    <th className="text-muted text-center py-2" style={{ fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 500 }}>Key</th>
                    <th className="text-muted py-2" style={{ fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 500 }}>Platforms</th>
                    <th className="text-muted py-2" style={{ fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.04em', fontWeight: 500 }}>Playlists</th>
                  </tr>
                </thead>
                <tbody>
                  {tracks.map(track => (
                    <TrackRow
                      key={track.canonical_id}
                      track={track}
                      analyzing={analyzingIds.has(track.canonical_id)}
                      analyzeAllRunning={analyzingIds.has('__analyze_all__')}
                      onAnalyze={handleAnalyze}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* ── Pagination ──────────────────────────────────────────────── */}
          <div className="d-flex align-items-center justify-content-between mt-3 flex-wrap gap-2">
            <small className="text-muted">
              Showing {startItem}–{endItem} of {total}
            </small>
            {pages > 1 && (
              <nav>
                <ul className="pagination pagination-sm mb-0">
                  <li className={`page-item ${page <= 1 ? 'disabled' : ''}`}>
                    <button className="page-link" onClick={() => handlePage(page - 1)}>‹</button>
                  </li>
                  {Array.from({ length: Math.min(pages, 7) }, (_, i) => {
                    let p
                    if (pages <= 7) {
                      p = i + 1
                    } else if (page <= 4) {
                      p = i + 1
                      if (i === 6) p = pages
                    } else if (page >= pages - 3) {
                      p = pages - 6 + i
                      if (i === 0) p = 1
                    } else {
                      const offsets = [0, page - 2, page - 1, page, page + 1, page + 2, pages - 1]
                      p = offsets[i] || i + 1
                    }
                    return (
                      <li key={i} className={`page-item ${p === page ? 'active' : ''}`}>
                        <button className="page-link" onClick={() => handlePage(p)}>{p}</button>
                      </li>
                    )
                  })}
                  <li className={`page-item ${page >= pages ? 'disabled' : ''}`}>
                    <button className="page-link" onClick={() => handlePage(page + 1)}>›</button>
                  </li>
                </ul>
              </nav>
            )}
          </div>
        </>
      )}
    </div>
  )
}
