import React, { useEffect, useRef, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  fetchPlaylists,
  createSyncJob,
  createMultiSyncJob,
  analyzeSyncJob,
  pollSyncJob,
  uploadTrack,
  skipTrack,
  confirmTrack,
  unconfirmTrack,
  confirmAllTracks,
  rejectTrack,
  selectMatch,
  resolveTrackUrl,
  pushToPlaylist,
  clearJob,
  clearError,
  // Match-level actions for multi-destination jobs
  confirmMatch,
  rejectMatch,
  selectMatchForDestination,
} from '../store/syncSlice'

// ── Source metadata ───────────────────────────────────────────────────────────

const SOURCE_META = {
  youtube_publish: { label: 'YouTube',    icon: 'bi-youtube',           color: 'text-danger'  },
  soundcloud:      { label: 'SoundCloud', icon: 'bi-soundwave',         color: 'text-warning' },
  spotify:         { label: 'Spotify',    icon: 'bi-music-note-beamed', color: 'text-success' },
  deezer:          { label: 'Deezer',     icon: 'bi-music-player',      color: 'text-primary' },
  local:           { label: 'Local',      icon: 'bi-folder',            color: 'text-secondary' },
  ftp:             { label: 'FTP',        icon: 'bi-server',            color: 'text-secondary' },
}

function sourceMeta(type) {
  return SOURCE_META[type] || { label: type, icon: 'bi-plug', color: 'text-muted' }
}

// ── Status config ─────────────────────────────────────────────────────────────

const TRACK_BADGE = {
  pending:   { cls: 'bg-secondary-subtle text-secondary border border-secondary-subtle', label: 'Pending' },
  matched:   { cls: 'bg-success-subtle text-success border border-success-subtle',       label: 'Matched' },
  uncertain: { cls: 'bg-warning-subtle text-warning border border-warning-subtle',       label: 'Uncertain' },
  not_found: { cls: 'bg-danger-subtle text-danger border border-danger-subtle',          label: 'Not Found' },
  uploading: { cls: 'bg-info-subtle text-info border border-info-subtle',                label: 'Uploading…' },
  uploaded:  { cls: 'bg-success-subtle text-success border border-success-subtle',       label: 'Uploaded' },
  skipped:   { cls: 'bg-light text-muted border',                                        label: 'Skipped' },
  failed:    { cls: 'bg-danger-subtle text-danger border border-danger-subtle',          label: 'Failed' },
}

const JOB_STATUS_BADGE = {
  pending:   { cls: 'bg-secondary',          label: 'Pending' },
  analyzing: { cls: 'bg-info',               label: 'Analyzing…' },
  ready:     { cls: 'bg-primary',            label: 'Ready' },
  syncing:   { cls: 'bg-warning text-dark',  label: 'Syncing…' },
  done:      { cls: 'bg-success',            label: 'Done' },
  failed:    { cls: 'bg-danger',             label: 'Failed' },
}

const POLLING_STATUSES = new Set(['analyzing', 'syncing'])

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtDuration(ms) {
  if (!ms) return '—'
  const s = Math.floor(ms / 1000)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

function confBadge(confidence) {
  if (confidence === null || confidence === undefined) return null
  const pct = Math.round(confidence * 100)
  const cls = confidence >= 0.90 ? 'text-success' : confidence >= 0.55 ? 'text-warning' : 'text-danger'
  return <span className={`small fw-semibold ${cls}`}>{pct}%</span>
}

// ── Sub-components ────────────────────────────────────────────────────────────

/**
 * Generic source selector — shows ALL available sources, optionally excluding one.
 * Options are grouped visually by showing `[TypeLabel] · Name`.
 */
function SourceSelect({ label, sources, excludeId, value, onChange }) {
  const available = sources.filter((s) => s.id !== excludeId)

  return (
    <div>
      <label className="form-label small fw-semibold text-muted text-uppercase">{label}</label>
      <select
        className="form-select form-select-sm"
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
      >
        <option value="">— choose account —</option>
        {available.map((s) => {
          const meta = sourceMeta(s.source_type)
          return (
            <option key={s.id} value={s.id}>
              {meta.label} · {s.name}
            </option>
          )
        })}
      </select>
      {/* Show icon of the selected source under the dropdown */}
      {value && (() => {
        const sel = sources.find((s) => s.id === value)
        if (!sel) return null
        const meta = sourceMeta(sel.source_type)
        return (
          <div className={`small mt-1 ${meta.color}`}>
            <i className={`bi ${meta.icon} me-1`}></i>
            <span className="text-muted">{sel.name}</span>
          </div>
        )
      })()}
    </div>
  )
}

function PlaylistBrowser({ playlists, loading, onSelect }) {
  if (loading) {
    return (
      <div className="text-center py-4 text-muted">
        <span className="spinner-border spinner-border-sm me-2" />Loading playlists…
      </div>
    )
  }

  if (!playlists?.length) {
    return <p className="text-muted small text-center py-3">No playlists found for this account.</p>
  }

  return (
    <div className="list-group list-group-flush" style={{ maxHeight: 320, overflowY: 'auto' }}>
      {playlists.map((pl) => (
        <button
          key={pl.id}
          className="list-group-item list-group-item-action d-flex justify-content-between align-items-center"
          onClick={() => onSelect(pl)}
        >
          <span>
            <i className="bi bi-collection-play me-2 text-warning"></i>
            {pl.name}
          </span>
          <span className="badge bg-secondary-subtle text-secondary border border-secondary-subtle rounded-pill">
            {pl.track_count ?? '?'} tracks
          </span>
        </button>
      ))}
    </div>
  )
}

// target_video_id holds the YouTube video ID for YT targets,
// the SoundCloud permalink URL for SC targets,
// or the bare Spotify track ID for Spotify targets.
const TARGET_LINK_CONFIG = {
  youtube_publish: {
    icon: 'bi-youtube',
    color: 'text-danger',
    href: (id) => `https://www.youtube.com/watch?v=${id}`,
  },
  soundcloud: {
    icon: 'bi-soundwave',
    color: 'text-warning',
    href: (id) => id, // stored as full permalink URL
  },
  spotify: {
    icon: 'bi-music-note-beamed',
    color: 'text-success',
    href: (id) => `https://open.spotify.com/track/${id}`,
  },
}

function TargetLink({ record, targetType }) {
  if (!record.target_title) {
    return record.status === 'not_found'
      ? <span className="text-muted fst-italic" style={{ fontSize: '0.78rem' }}>No match found</span>
      : null
  }

  const cfg = TARGET_LINK_CONFIG[targetType]
  if (cfg && record.target_video_id) {
    return (
      <a
        href={cfg.href(record.target_video_id)}
        target="_blank"
        rel="noreferrer"
        className="text-decoration-none text-truncate d-inline-block"
        style={{ maxWidth: 200 }}
        title={record.target_title}
      >
        <i className={`bi ${cfg.icon} ${cfg.color} me-1`}></i>
        {record.target_title}
      </a>
    )
  }

  return <span className="text-muted small text-truncate d-inline-block" style={{ maxWidth: 200 }}>{record.target_title}</span>
}

function TrackRowInner({ track, jobId, sourceType, targetType, dispatch }) {
  const [busy, setBusy] = React.useState(false)  // local spinner for confirm/reject

  const badge = TRACK_BADGE[track.status] || TRACK_BADGE.pending
  const hasMatch = !!track.target_video_id
  const canValidate = hasMatch && ['matched', 'uncertain'].includes(track.status)
  const confirmed = track.user_feedback === 'confirmed'
  const canUpload = track.status === 'uncertain' || track.status === 'not_found'

  async function handleConfirm() {
    setBusy(true)
    await dispatch(confirmTrack({ jobId, trackId: track.id }))
    setBusy(false)
  }

  async function handleUnconfirm() {
    setBusy(true)
    await dispatch(unconfirmTrack({ jobId, trackId: track.id }))
    setBusy(false)
  }

  async function handleReject() {
    setBusy(true)
    await dispatch(rejectTrack({ jobId, trackId: track.id }))
    setBusy(false)
  }

  return (
    <tr className={confirmed ? 'table-success' : ''}>
      <td className="align-middle" style={{ width: 40 }}>
        {track.source_artwork_url
          ? <img src={track.source_artwork_url} alt="" width={36} height={36} className="rounded" style={{ objectFit: 'cover' }} />
          : <div className="bg-secondary-subtle rounded d-flex align-items-center justify-content-center" style={{ width: 36, height: 36 }}>
              <i className="bi bi-music-note text-secondary"></i>
            </div>
        }
      </td>
      <td className="align-middle">
        {track.source_permalink_url ? (
          <a
            href={track.source_permalink_url}
            target="_blank"
            rel="noreferrer"
            className="fw-semibold small text-truncate d-block text-decoration-none text-body"
            style={{ maxWidth: 220 }}
            title={track.source_title}
          >
            {sourceType && (() => {
              const m = sourceMeta(sourceType)
              return <i className={`bi ${m.icon} ${m.color} me-1`}></i>
            })()}
            {track.source_title}
          </a>
        ) : (
          <div className="fw-semibold small text-truncate" style={{ maxWidth: 220 }}>{track.source_title}</div>
        )}
        <div className="text-muted" style={{ fontSize: '0.78rem' }}>{track.source_artist}</div>
      </td>
      <td className="align-middle text-muted small">{fmtDuration(track.source_duration_ms)}</td>
      <td className="align-middle">
        <div className="d-flex flex-column gap-1">
          <span className={`badge rounded-pill ${badge.cls}`} style={{ fontSize: '0.72rem' }}>
            {badge.label}
          </span>
          {confirmed && (
            <span className="badge rounded-pill bg-success-subtle text-success border border-success-subtle" style={{ fontSize: '0.68rem' }}>
              <i className="bi bi-hand-thumbs-up-fill me-1"></i>Confirmed
            </span>
          )}
        </div>
      </td>
      <td className="align-middle">
        {track.match_confidence != null && confBadge(track.match_confidence)}
      </td>
      <td className="align-middle small" style={{ maxWidth: 200 }}>
        <TargetLink record={track} targetType={targetType} />
        {track.has_alternatives && track.status !== 'not_found' && !confirmed && (
          <div className="text-muted" style={{ fontSize: '0.68rem' }}>
            <i className="bi bi-collection me-1"></i>alternatives available
          </div>
        )}
        {track.status === 'not_found' && track.search_results?.length > 0 && (
          <div className="text-muted" style={{ fontSize: '0.68rem' }}>
            <i className="bi bi-search me-1"></i>{track.search_results.length} search result{track.search_results.length !== 1 ? 's' : ''} below
          </div>
        )}
        {track.error && (
          <span className="text-danger d-block" style={{ fontSize: '0.72rem' }} title={track.error}>
            <i className="bi bi-exclamation-circle me-1"></i>{track.error.slice(0, 60)}
          </span>
        )}
      </td>
      <td className="align-middle text-end" style={{ minWidth: 160 }}>
        {busy ? (
          <span className="spinner-border spinner-border-sm text-primary" />
        ) : (
          <div className="d-flex flex-column gap-1 align-items-end">
            {/* Confirm / Reject buttons — appear for any matched/uncertain track */}
            {canValidate && !confirmed && (
              <div className="d-flex gap-1">
                <button
                  className="btn btn-sm btn-success"
                  style={{ fontSize: '0.72rem', padding: '2px 10px' }}
                  title="This is the correct match"
                  onClick={handleConfirm}
                >
                  <i className="bi bi-check-lg me-1"></i>Confirm
                </button>
                <button
                  className="btn btn-sm btn-outline-danger"
                  style={{ fontSize: '0.72rem', padding: '2px 8px' }}
                  title="Not the right track — show next alternative"
                  onClick={handleReject}
                >
                  <i className="bi bi-x-lg"></i>
                </button>
              </div>
            )}

            {/* Unvalidate — shown when track is already confirmed */}
            {confirmed && (
              <button
                className="btn btn-sm btn-outline-secondary"
                style={{ fontSize: '0.72rem', padding: '2px 8px' }}
                title="Remove confirmation"
                onClick={handleUnconfirm}
              >
                <i className="bi bi-x-circle me-1"></i>Unvalidate
              </button>
            )}

            {/* Upload / Skip — appear for uncertain and not_found */}
            {canUpload && (
              <div className="d-flex gap-1">
                <button
                  className="btn btn-sm btn-outline-primary"
                  style={{ fontSize: '0.72rem', padding: '2px 8px' }}
                  onClick={() => dispatch(uploadTrack({ jobId, trackId: track.id }))}
                >
                  <i className="bi bi-cloud-upload me-1"></i>Upload
                </button>
                <button
                  className="btn btn-sm btn-outline-secondary"
                  style={{ fontSize: '0.72rem', padding: '2px 8px' }}
                  onClick={() => dispatch(skipTrack({ jobId, trackId: track.id }))}
                >
                  Skip
                </button>
              </div>
            )}
          </div>
        )}
        {track.status === 'uploading' && !busy && (
          <span className="spinner-border spinner-border-sm text-info" />
        )}
      </td>
    </tr>
  )
}

const PLATFORM_SEARCH_URL = {
  youtube_publish: (q) => `https://www.youtube.com/results?search_query=${encodeURIComponent(q)}`,
  soundcloud:      (q) => `https://soundcloud.com/search?q=${encodeURIComponent(q)}`,
  spotify:         (q) => `https://open.spotify.com/search/${encodeURIComponent(q)}`,
}

function SearchResultsRow({ track, jobId, targetType, dispatch }) {
  const baseResults = track.search_results || []
  const [extraResults, setExtraResults] = useState([])
  const [urlInput, setUrlInput] = useState('')
  const [urlError, setUrlError] = useState('')
  const [urlLoading, setUrlLoading] = useState(false)

  const results = [...baseResults, ...extraResults]

  const cfg = TARGET_LINK_CONFIG[targetType]
  const searchQuery = [track.source_title, track.source_artist].filter(Boolean).join(' ')
  const platformSearchUrl = PLATFORM_SEARCH_URL[targetType]?.(searchQuery)

  async function handlePick(videoId) {
    await dispatch(selectMatch({ jobId, trackId: track.id, videoId }))
  }

  async function handleAddUrl(e) {
    e.preventDefault()
    const url = urlInput.trim()
    if (!url) return
    setUrlError('')
    setUrlLoading(true)
    const result = await dispatch(resolveTrackUrl({ jobId, trackId: track.id, url }))
    setUrlLoading(false)
    if (resolveTrackUrl.fulfilled.match(result)) {
      const resolved = result.payload
      const alreadyIn = results.some((r) => r.video_id === resolved.video_id)
      if (!alreadyIn) {
        setExtraResults((prev) => [...prev, { ...resolved, confidence: 0 }])
      }
      setUrlInput('')
    } else {
      setUrlError(result.payload || 'Could not resolve URL')
    }
  }

  return (
    <tr className="table-danger" style={{ borderTop: 'none' }}>
      <td colSpan={7} className="py-2 px-3" style={{ borderTop: 'none' }}>
        <div className="d-flex align-items-center gap-2 mb-1" style={{ fontSize: '0.75rem' }}>
          <i className="bi bi-search text-danger"></i>
          <span className="fw-semibold text-danger">Search results</span>
          <span className="text-muted">— pick the correct match for <em>{track.source_title}</em></span>
        </div>
        <div className="d-flex flex-column gap-1">
          {results.map((r) => (
            <div
              key={r.video_id}
              className="d-flex align-items-center gap-2 px-2 py-1 rounded"
              style={{ background: 'rgba(0,0,0,0.03)', fontSize: '0.78rem' }}
            >
              {cfg && r.video_id ? (
                <a
                  href={cfg.href(r.video_id)}
                  target="_blank"
                  rel="noreferrer"
                  className={`text-decoration-none flex-shrink-0 ${cfg.color}`}
                  title="Open on platform"
                >
                  <i className={`bi ${cfg.icon}`}></i>
                </a>
              ) : (
                <i className="bi bi-music-note text-secondary flex-shrink-0"></i>
              )}
              <div className="d-flex flex-column text-truncate flex-grow-1" style={{ maxWidth: 280 }}>
                <span className="fw-semibold text-truncate">{r.title}</span>
                {r.artist && (
                  <span className="text-truncate" style={{ fontSize: '0.7rem', color: '#6c757d' }}>
                    {r.artist}
                  </span>
                )}
              </div>
              <span className="text-muted flex-shrink-0" style={{ minWidth: 36 }}>
                {Math.round((r.confidence || 0) * 100)}%
              </span>
              <button
                className="btn btn-sm btn-outline-success flex-shrink-0"
                style={{ fontSize: '0.7rem', padding: '1px 8px' }}
                onClick={() => handlePick(r.video_id)}
              >
                Pick
              </button>
            </div>
          ))}
        </div>

        {/* URL paste input */}
        <form onSubmit={handleAddUrl} className="mt-2">
          <div className={`input-group input-group-sm${urlError ? ' is-invalid' : ''}`}>
            {platformSearchUrl && (
              <a
                href={platformSearchUrl}
                target="_blank"
                rel="noreferrer"
                className={`btn btn-sm btn-outline-secondary d-flex align-items-center gap-1 ${cfg?.color ?? ''}`}
                style={{ fontSize: '0.72rem' }}
                title={`Search "${searchQuery}" on ${sourceMeta(targetType).label}`}
              >
                <i className={`bi ${cfg?.icon ?? 'bi-box-arrow-up-right'}`}></i>
                Search on {sourceMeta(targetType).label}
              </a>
            )}
            <input
              type="url"
              className={`form-control form-control-sm${urlError ? ' is-invalid' : ''}`}
              style={{ fontSize: '0.75rem' }}
              placeholder={`Paste a ${sourceMeta(targetType).label} track URL…`}
              value={urlInput}
              onChange={(e) => { setUrlInput(e.target.value); setUrlError('') }}
              disabled={urlLoading}
            />
            <button
              type="submit"
              className="btn btn-sm btn-outline-secondary"
              style={{ fontSize: '0.72rem' }}
              disabled={urlLoading || !urlInput.trim()}
            >
              {urlLoading ? <span className="spinner-border spinner-border-sm" /> : 'Add'}
            </button>
          </div>
          {urlError && <div className="text-danger mt-1" style={{ fontSize: '0.72rem' }}>{urlError}</div>}
        </form>
      </td>
    </tr>
  )
}

function TrackRow({ track, jobId, sourceType, targetType, dispatch }) {
  return (
    <>
      <TrackRowInner track={track} jobId={jobId} sourceType={sourceType} targetType={targetType} dispatch={dispatch} />
      {track.status === 'not_found' && (
        <SearchResultsRow track={track} jobId={jobId} targetType={targetType} dispatch={dispatch} />
      )}
    </>
  )
}

function DestinationMatchCell({ match, destination, jobId, dispatch }) {
  const [busy, setBusy] = React.useState(false)

  if (!match) {
    return (
      <td className="align-middle text-muted small">
        <span className="fst-italic">No analysis yet</span>
      </td>
    )
  }

  const badge = TRACK_BADGE[match.status] || TRACK_BADGE.pending
  const canValidate =
    !!match.target_video_id &&
    ['matched', 'uncertain', 'uploaded'].includes(match.status)
  const confirmed = match.user_feedback === 'confirmed'

  async function handleConfirm() {
    setBusy(true)
    await dispatch(confirmMatch({ jobId, matchId: match.id }))
    setBusy(false)
  }

  async function handleReject() {
    setBusy(true)
    await dispatch(rejectMatch({ jobId, matchId: match.id }))
    setBusy(false)
  }

  return (
    <td className="align-middle small" style={{ minWidth: 180 }}>
      <div className="d-flex flex-column gap-1">
        <div className="d-flex align-items-center justify-content-between gap-2">
          <span className={`badge rounded-pill ${badge.cls}`} style={{ fontSize: '0.72rem' }}>
            {badge.label}
          </span>
          {match.match_confidence != null && confBadge(match.match_confidence)}
        </div>
        <div>
          <TargetLink record={match} targetType={destination.source.source_type} />
          {match.error && (
            <div className="text-danger mt-1" style={{ fontSize: '0.7rem' }}>
              <i className="bi bi-exclamation-circle me-1"></i>
              {match.error.slice(0, 60)}
            </div>
          )}
        </div>
        <div className="d-flex justify-content-end gap-1">
          {busy ? (
            <span className="spinner-border spinner-border-sm text-primary" />
          ) : (
            <>
              {canValidate && !confirmed && (
                <>
                  <button
                    className="btn btn-sm btn-success"
                    style={{ fontSize: '0.72rem', padding: '2px 8px' }}
                    title="Confirm this match for this destination"
                    onClick={handleConfirm}
                  >
                    <i className="bi bi-check-lg me-1"></i>Confirm
                  </button>
                  {match.has_alternatives && (
                    <button
                      className="btn btn-sm btn-outline-danger"
                      style={{ fontSize: '0.72rem', padding: '2px 6px' }}
                      title="Not the right track — try next alternative"
                      onClick={handleReject}
                    >
                      <i className="bi bi-x-lg"></i>
                    </button>
                  )}
                </>
              )}
              {confirmed && (
                <span className="badge rounded-pill bg-success-subtle text-success border border-success-subtle" style={{ fontSize: '0.68rem' }}>
                  <i className="bi bi-hand-thumbs-up-fill me-1"></i>Confirmed
                </span>
              )}
            </>
          )}
        </div>
      </div>
    </td>
  )
}

function MultiDestinationTrackRow({ track, jobId, sourceType, destinations, dispatch }) {
  return (
    <tr>
      <td className="align-middle" style={{ width: 40 }}>
        {track.source_artwork_url
          ? <img src={track.source_artwork_url} alt="" width={36} height={36} className="rounded" style={{ objectFit: 'cover' }} />
          : (
            <div className="bg-secondary-subtle rounded d-flex align-items-center justify-content-center" style={{ width: 36, height: 36 }}>
              <i className="bi bi-music-note text-secondary"></i>
            </div>
          )
        }
      </td>
      <td className="align-middle">
        {track.source_permalink_url ? (
          <a
            href={track.source_permalink_url}
            target="_blank"
            rel="noreferrer"
            className="fw-semibold small text-truncate d-block text-decoration-none text-body"
            style={{ maxWidth: 220 }}
            title={track.source_title}
          >
            {sourceType && (() => {
              const m = sourceMeta(sourceType)
              return <i className={`bi ${m.icon} ${m.color} me-1`}></i>
            })()}
            {track.source_title}
          </a>
        ) : (
          <div className="fw-semibold small text-truncate" style={{ maxWidth: 220 }}>{track.source_title}</div>
        )}
        <div className="text-muted" style={{ fontSize: '0.78rem' }}>{track.source_artist}</div>
      </td>
      <td className="align-middle text-muted small">
        {fmtDuration(track.source_duration_ms)}
      </td>
      {destinations.map((dest) => {
        const match = (track.destination_matches || []).find(
          (m) => m.destination_id === dest.id,
        )
        return (
          <DestinationMatchCell
            key={dest.id}
            match={match}
            destination={dest}
            jobId={jobId}
            dispatch={dispatch}
          />
        )
      })}
    </tr>
  )
}

function PushToPlaylist({ job, targetPlaylists, targetPlaylistsLoading, dispatch }) {
  const { pushLoading } = useSelector((s) => s.sync)

  const tracks = job.tracks || []
  const syncPlaylists = job.sync_playlists || []
  const destinationPlaylists = syncPlaylists.filter(
    (sp) => sp.role === 'destination' || sp.role === 'both',
  )

  const [configs, setConfigs] = useState(() =>
    destinationPlaylists.map((dest) => ({
      destinationId: dest.id,
      mode: 'existing',      // 'existing' | 'new'
      selectedId: '',
      newName: dest.playlist_name || '',
    })),
  )

  function updateConfig(destinationId, patch) {
    setConfigs((prev) =>
      prev.map((c) =>
        c.destinationId === destinationId ? { ...c, ...patch } : c,
      ),
    )
  }

  function eligibleForDestination(dest) {
    const destMatchesByTrack = {}
    for (const t of tracks) {
      const m = (t.destination_matches || []).find((x) => x.destination_id === dest.id)
      if (m) destMatchesByTrack[t.id] = m
    }
    const matches = Object.values(destMatchesByTrack)
    return matches.filter(
      (m) =>
        m.target_video_id &&
        (
          m.status === 'matched' ||
          m.status === 'uploaded' ||
          (m.status === 'uncertain' && m.user_feedback === 'confirmed')
        ),
    )
  }

  // Legacy jobs fallback: no sync_playlists → show original single-destination panel
  if (!destinationPlaylists.length) {
    const [mode, setMode] = useState('existing')
    const [selectedId, setSelectedId] = useState('')
    const [newName, setNewName] = useState('')

    const eligibleTracks = tracks.filter(
      (t) =>
        t.target_video_id &&
        (
          t.status === 'matched' ||
          t.status === 'uploaded' ||
          (t.status === 'uncertain' && t.user_feedback === 'confirmed')
        ),
    )
    const pushedCount = tracks.filter((t) => t.pushed_to_playlist).length

    function handleLegacyPush() {
      const payload = {
        jobId: job.id,
        targetPlaylistId: mode === 'existing' ? selectedId : null,
        newPlaylistName: mode === 'new' ? newName.trim() : '',
      }
      dispatch(pushToPlaylist(payload))
    }

    const canPushLegacy =
      mode === 'existing'
        ? !!selectedId
        : newName.trim().length > 0

    if (job.pushed_at && job.target_playlist_name) {
      const pushedDate = new Date(job.pushed_at).toLocaleDateString()
      return (
        <div className="card-body pt-0">
          <div className="alert alert-success mb-0 py-2 d-flex align-items-center gap-2">
            <i className="bi bi-check-circle-fill fs-5"></i>
            <div>
              <span className="fw-semibold">Pushed to "{job.target_playlist_name}"</span>
              <span className="text-muted ms-2 small">on {pushedDate}</span>
              {pushedCount > 0 && (
                <span className="ms-2 small">· {pushedCount} track{pushedCount !== 1 ? 's' : ''} added</span>
              )}
            </div>
          </div>
        </div>
      )
    }

    return (
      <div className="card-body border-top pt-3">
        <h6 className="fw-semibold mb-3">
          <i className="bi bi-send me-2 text-primary"></i>Push to Playlist
        </h6>
        {/* Legacy single-destination controls */}
        <div className="d-flex gap-3 mb-3">
          <div className="form-check">
            <input
              className="form-check-input"
              type="radio"
              id="legacyModeExisting"
              checked={mode === 'existing'}
              onChange={() => setMode('existing')}
            />
            <label className="form-check-label small" htmlFor="legacyModeExisting">
              Add to existing playlist
            </label>
          </div>
          <div className="form-check">
            <input
              className="form-check-input"
              type="radio"
              id="legacyModeNew"
              checked={mode === 'new'}
              onChange={() => setMode('new')}
            />
            <label className="form-check-label small" htmlFor="legacyModeNew">
              Create new playlist
            </label>
          </div>
        </div>

        {mode === 'existing' && (
          <div className="mb-3" style={{ maxHeight: 220, overflowY: 'auto', border: '1px solid var(--bs-border-color)', borderRadius: 6 }}>
            {targetPlaylistsLoading ? (
              <div className="text-center py-3 text-muted small">
                <span className="spinner-border spinner-border-sm me-2" />Loading playlists…
              </div>
            ) : targetPlaylists.length === 0 ? (
              <p className="text-muted small text-center py-3 mb-0">No playlists found.</p>
            ) : (
              <div className="list-group list-group-flush">
                {targetPlaylists.map((pl) => (
                  <button
                    key={pl.id}
                    className={`list-group-item list-group-item-action d-flex justify-content-between align-items-center py-2 ${selectedId === pl.id ? 'active' : ''}`}
                    onClick={() => setSelectedId(pl.id)}
                  >
                    <span className="small">{pl.name}</span>
                    <span className="badge bg-secondary-subtle text-secondary border rounded-pill" style={{ fontSize: '0.68rem' }}>
                      {pl.track_count ?? '?'}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {mode === 'new' && (
          <div className="mb-3">
            <input
              type="text"
              className="form-control form-control-sm"
              placeholder="New playlist name…"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
          </div>
        )}

        <div className="d-flex align-items-center justify-content-between">
          <span className="small text-muted">
            <i className="bi bi-music-note-list me-1"></i>
            Will add <strong>{eligibleTracks.length}</strong> track{eligibleTracks.length !== 1 ? 's' : ''}
            {tracks.filter((t) => t.status === 'skipped').length > 0 && (
              <span className="ms-1">(skipping {tracks.filter((t) => t.status === 'skipped').length} skipped)</span>
            )}
          </span>
          <button
            className="btn btn-primary btn-sm"
            disabled={!canPushLegacy || pushLoading || eligibleTracks.length === 0}
            onClick={handleLegacyPush}
          >
            {pushLoading
              ? <><span className="spinner-border spinner-border-sm me-1" />Adding tracks…</>
              : <><i className="bi bi-send me-1"></i>Validate Sync</>
            }
          </button>
        </div>
      </div>
    )
  }

  // Multi-destination UI
  return (
    <div className="card-body border-top pt-3">
      <h6 className="fw-semibold mb-3">
        <i className="bi bi-send me-2 text-primary"></i>Push to Destinations
      </h6>
      <div className="row g-3">
        {destinationPlaylists.map((dest) => {
          const meta = sourceMeta(dest.source.source_type)
          const cfg = configs.find((c) => c.destinationId === dest.id) || {
            destinationId: dest.id,
            mode: 'existing',
            selectedId: '',
            newName: dest.playlist_name || '',
          }
          const eligible = eligibleForDestination(dest)

          const canPush =
            cfg.mode === 'existing'
              ? !!cfg.selectedId
              : cfg.newName.trim().length > 0

          function handlePushOne() {
            const payload = {
              jobId: job.id,
              destinationId: dest.id,
              targetPlaylistId: cfg.mode === 'existing' ? cfg.selectedId : null,
              newPlaylistName: cfg.mode === 'new' ? cfg.newName.trim() : '',
            }
            dispatch(pushToPlaylist(payload))
          }

          return (
            <div key={dest.id} className="col-md-6">
              <div className="border rounded p-2 h-100">
                <div className="d-flex align-items-center justify-content-between mb-2">
                  <div>
                    <div className={`small fw-semibold ${meta.color}`}>
                      <i className={`bi ${meta.icon} me-1`}></i>
                      {dest.source.name}
                    </div>
                    {dest.playlist_name && (
                      <div className="text-muted small text-truncate">
                        {dest.playlist_name}
                      </div>
                    )}
                  </div>
                  <span className="badge bg-light text-muted border" style={{ fontSize: '0.7rem' }}>
                    {eligible.length} ready track{eligible.length !== 1 ? 's' : ''}
                  </span>
                </div>

                {/* Mode toggle */}
                <div className="d-flex gap-3 mb-2">
                  <div className="form-check">
                    <input
                      className="form-check-input"
                      type="radio"
                      id={`dest-${dest.id}-existing`}
                      checked={cfg.mode === 'existing'}
                      onChange={() => updateConfig(dest.id, { mode: 'existing' })}
                    />
                    <label className="form-check-label small" htmlFor={`dest-${dest.id}-existing`}>
                      Existing playlist
                    </label>
                  </div>
                  <div className="form-check">
                    <input
                      className="form-check-input"
                      type="radio"
                      id={`dest-${dest.id}-new`}
                      checked={cfg.mode === 'new'}
                      onChange={() => updateConfig(dest.id, { mode: 'new' })}
                    />
                    <label className="form-check-label small" htmlFor={`dest-${dest.id}-new`}>
                      New playlist
                    </label>
                  </div>
                </div>

                {cfg.mode === 'new' && (
                  <div className="mb-2">
                    <input
                      type="text"
                      className="form-control form-control-sm"
                      placeholder="New playlist name…"
                      value={cfg.newName}
                      onChange={(e) => updateConfig(dest.id, { newName: e.target.value })}
                    />
                  </div>
                )}

                {/* For now we don't have per-destination playlist browsing; keep it simple */}

                <div className="d-flex align-items-center justify-content-between mt-2">
                  <span className="small text-muted">
                    <i className="bi bi-music-note-list me-1"></i>
                    Will add <strong>{eligible.length}</strong> track{eligible.length !== 1 ? 's' : ''}
                  </span>
                  <button
                    className="btn btn-primary btn-sm"
                    disabled={!canPush || pushLoading || eligible.length === 0}
                    onClick={handlePushOne}
                  >
                    {pushLoading
                      ? <><span className="spinner-border spinner-border-sm me-1" />Pushing…</>
                      : <><i className="bi bi-send me-1"></i>Push</>
                    }
                  </button>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function JobProgress({ job }) {
  const tracks = job.tracks || []
  const total = tracks.length
  if (!total) return null

  const done     = tracks.filter((t) => ['matched', 'uploaded', 'skipped', 'not_found', 'failed'].includes(t.status)).length
  const uploaded = tracks.filter((t) => t.status === 'uploaded').length
  const uncertain = tracks.filter((t) => t.status === 'uncertain').length
  const notFound = tracks.filter((t) => t.status === 'not_found').length
  const matched  = tracks.filter((t) => t.status === 'matched').length
  const pct = Math.round((done / total) * 100)

  return (
    <div className="mb-3">
      <div className="d-flex justify-content-between align-items-center mb-1">
        <span className="small text-muted">Analysis progress</span>
        <span className="small fw-semibold">{done}/{total}</span>
      </div>
      <div className="progress" style={{ height: 6 }}>
        <div className="progress-bar bg-success" style={{ width: `${pct}%` }} />
      </div>
      <div className="d-flex gap-3 mt-2 small text-muted flex-wrap">
        <span><i className="bi bi-check-circle text-success me-1"></i>{matched} matched</span>
        <span><i className="bi bi-question-circle text-warning me-1"></i>{uncertain} uncertain</span>
        <span><i className="bi bi-x-circle text-danger me-1"></i>{notFound} not found</span>
        <span><i className="bi bi-cloud-upload text-info me-1"></i>{uploaded} uploaded</span>
      </div>
    </div>
  )
}

// ── Role configuration helpers ────────────────────────────────────────────────

const ROLE_OPTIONS = [
  { value: 'source',      label: 'Source',        icon: 'bi-box-arrow-right',   color: 'text-info',    desc: 'Tracks are read from here' },
  { value: 'destination', label: 'Destination',   icon: 'bi-box-arrow-in-right', color: 'text-warning', desc: 'Tracks are synced to here' },
  { value: 'both',        label: 'Bidirectional', icon: 'bi-arrow-left-right',  color: 'text-primary', desc: 'Sync in both directions' },
]

function RoleSelector({ role, onChange }) {
  return (
    <div className="btn-group btn-group-sm" role="group">
      {ROLE_OPTIONS.map((opt) => (
        <button
          key={opt.value}
          type="button"
          className={`btn ${role === opt.value ? 'btn-primary' : 'btn-outline-secondary'}`}
          onClick={() => onChange(opt.value)}
          title={opt.desc}
        >
          <i className={`bi ${opt.icon} me-1`}></i>
          {opt.label}
        </button>
      ))}
    </div>
  )
}

// ── Step indicator ────────────────────────────────────────────────────────────

function StepIndicator({ currentStep, onStepClick, selectedCount }) {
  const steps = [
    { num: 1, label: 'Select Playlists', icon: 'bi-collection-play', enabled: true },
    { num: 2, label: 'Configure Roles',  icon: 'bi-sliders',         enabled: selectedCount > 0 },
  ]

  return (
    <div className="d-flex align-items-center gap-2 mb-3">
      {steps.map((step, idx) => (
        <React.Fragment key={step.num}>
          {idx > 0 && (
            <div
              className={`flex-grow-0 ${currentStep > step.num - 1 ? 'bg-primary' : 'bg-secondary-subtle'}`}
              style={{ height: 2, width: 40 }}
            />
          )}
          <button
            type="button"
            className={`btn btn-sm d-flex align-items-center gap-2 ${
              currentStep === step.num
                ? 'btn-primary'
                : currentStep > step.num
                  ? 'btn-outline-primary'
                  : 'btn-outline-secondary'
            }`}
            disabled={!step.enabled}
            onClick={() => step.enabled && onStepClick(step.num)}
            style={{ minWidth: 160 }}
          >
            <span
              className="d-inline-flex align-items-center justify-content-center rounded-circle"
              style={{
                width: 24,
                height: 24,
                fontSize: '0.75rem',
                fontWeight: 700,
                background: currentStep === step.num ? 'rgba(255,255,255,0.2)' : 'transparent',
              }}
            >
              {currentStep > step.num
                ? <i className="bi bi-check-lg"></i>
                : step.num}
            </span>
            <span className="small fw-semibold">{step.label}</span>
          </button>
        </React.Fragment>
      ))}
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function SyncPage() {
  const dispatch = useDispatch()
  const { items: sources } = useSelector((s) => s.sources)
  const {
    playlists,
    playlistsLoading,
    playlistsLoadingById,
    job,
    jobLoading,
    pushLoading,
    error,
  } = useSelector((s) => s.sync)

  const [wizardStep, setWizardStep] = useState(1)        // 1 = select playlists, 2 = configure roles
  const [browseAccountId, setBrowseAccountId] = useState(null)
  // Each entry: { source_id, playlist_id, playlist_name, role: 'source'|'destination'|'both' }
  const [selectedPlaylists, setSelectedPlaylists] = useState([])

  const pollRef = useRef(null)

  useEffect(() => {
    if (browseAccountId) dispatch(fetchPlaylists(browseAccountId))
  }, [browseAccountId, dispatch])

  useEffect(() => {
    if (job && POLLING_STATUSES.has(job.status)) {
      pollRef.current = setInterval(() => dispatch(pollSyncJob(job.id)), 3000)
    } else {
      clearInterval(pollRef.current)
    }
    return () => clearInterval(pollRef.current)
  }, [job?.id, job?.status, dispatch])

  function plKey(p) { return `${p.source_id}:${p.playlist_id}` }

  function isSelected(sourceId, playlistId) {
    return selectedPlaylists.some((p) => p.source_id === sourceId && p.playlist_id === playlistId)
  }

  function togglePlaylist(pl) {
    if (!browseAccountId) return
    setSelectedPlaylists((prev) => {
      const key = `${browseAccountId}:${pl.id}`
      const exists = prev.find((p) => plKey(p) === key)
      if (exists) return prev.filter((p) => plKey(p) !== key)
      return [...prev, {
        source_id: browseAccountId,
        playlist_id: pl.id,
        playlist_name: pl.name,
        role: 'source',
      }]
    })
    dispatch(clearJob())
  }

  function removePlaylist(sourceId, playlistId) {
    setSelectedPlaylists((prev) =>
      prev.filter((p) => !(p.source_id === sourceId && p.playlist_id === playlistId)),
    )
  }

  function setPlaylistRole(sourceId, playlistId, role) {
    setSelectedPlaylists((prev) =>
      prev.map((p) =>
        p.source_id === sourceId && p.playlist_id === playlistId
          ? { ...p, role }
          : p,
      ),
    )
  }

  function setAllRoles(role) {
    setSelectedPlaylists((prev) => prev.map((p) => ({ ...p, role })))
  }

  async function handleStartSync() {
    if (!selectedPlaylists.length) return
    const hasSrc = selectedPlaylists.some((p) => p.role === 'source' || p.role === 'both')
    const hasDst = selectedPlaylists.some((p) => p.role === 'destination' || p.role === 'both')
    if (!hasSrc || !hasDst) return

    const result = await dispatch(
      createMultiSyncJob({
        playlists: selectedPlaylists.map(({ source_id, playlist_id, playlist_name, role }) => ({
          source_id, playlist_id, playlist_name, role,
        })),
      }),
    )
    if (result.meta.requestStatus === 'fulfilled') {
      dispatch(analyzeSyncJob(result.payload.id))
    }
  }

  function handleReset() {
    dispatch(clearJob())
    setSelectedPlaylists([])
    setWizardStep(1)
  }

  const fromLoading = browseAccountId
    ? playlistsLoadingById?.[browseAccountId] ?? !(browseAccountId in playlists)
    : false
  const currentPlaylists = browseAccountId ? playlists[browseAccountId] || [] : []
  const targetPlaylists = []
  const jobBadge = job ? (JOB_STATUS_BADGE[job.status] || JOB_STATUS_BADGE.pending) : null
  const tracks = job?.tracks || []
  const targetType = job?.source_to?.source_type || null

  const syncPlaylists = job?.sync_playlists || []
  const destinationPlaylists = syncPlaylists.filter(
    (sp) => sp.role === 'destination' || sp.role === 'both',
  )
  const isMultiDestinationJob = destinationPlaylists.length > 0 && tracks.some(
    (t) => Array.isArray(t.destination_matches) && t.destination_matches.length > 0,
  )

  const unconfirmedMatchCount = tracks.filter(
    (t) => ['matched', 'uncertain'].includes(t.status) && t.target_video_id && t.user_feedback !== 'confirmed'
  ).length

  const targetMeta = targetType ? sourceMeta(targetType) : null
  const matchColHeader = targetMeta
    ? <><i className={`bi ${targetMeta.icon} ${targetMeta.color} me-1`}></i>Match on {targetMeta.label}</>
    : 'Match'

  const noSources = sources.length < 2

  const srcCount = selectedPlaylists.filter((p) => p.role === 'source' || p.role === 'both').length
  const dstCount = selectedPlaylists.filter((p) => p.role === 'destination' || p.role === 'both').length
  const canStart = srcCount > 0 && dstCount > 0

  return (
    <div className="row justify-content-center mt-4">
      <div className="col-xl-10 col-lg-12">

        {error && (
          <div className="alert alert-danger alert-dismissible mb-3" role="alert">
            <i className="bi bi-exclamation-circle me-2"></i>{error}
            <button type="button" className="btn-close" onClick={() => dispatch(clearError())} />
          </div>
        )}

        {noSources && (
          <div className="alert alert-info mb-3">
            <i className="bi bi-info-circle me-2"></i>
            Connect at least <strong>two accounts</strong> in the sidebar to sync between them.
          </div>
        )}

        {/* ── Setup Card (2-step wizard) ── */}
        <div className="card shadow-sm mb-3">
          <div className="card-header d-flex align-items-center justify-content-between">
            <span className="fw-semibold">
              <i className="bi bi-arrow-left-right me-2 text-primary"></i>Sync Setup
            </span>
            {job && (
              <button className="btn btn-sm btn-outline-secondary" onClick={handleReset}>
                <i className="bi bi-arrow-counterclockwise me-1"></i>New sync
              </button>
            )}
          </div>
          <div className="card-body">
            <StepIndicator
              currentStep={wizardStep}
              onStepClick={setWizardStep}
              selectedCount={selectedPlaylists.length}
            />

            {/* ── STEP 1: Select Playlists ── */}
            {wizardStep === 1 && (
              <div>
                <div className="row g-3 align-items-start">
                  {/* Account selector */}
                  <div className="col-md-4">
                    <label className="form-label small fw-semibold text-muted text-uppercase">
                      Browse account
                    </label>
                    <div className="d-flex flex-column gap-1">
                      {sources.map((s) => {
                        const meta = sourceMeta(s.source_type)
                        const active = browseAccountId === s.id
                        const countForAccount = selectedPlaylists.filter((p) => p.source_id === s.id).length
                        return (
                          <button
                            key={s.id}
                            type="button"
                            className={`btn btn-sm text-start d-flex align-items-center justify-content-between ${
                              active ? 'btn-primary' : 'btn-outline-secondary'
                            }`}
                            onClick={() => setBrowseAccountId(s.id)}
                          >
                            <span>
                              <i className={`bi ${meta.icon} me-2`}></i>
                              {s.name}
                            </span>
                            {countForAccount > 0 && (
                              <span className={`badge rounded-pill ${active ? 'bg-light text-primary' : 'bg-primary-subtle text-primary'}`}>
                                {countForAccount}
                              </span>
                            )}
                          </button>
                        )
                      })}
                    </div>
                  </div>

                  {/* Playlist browser with checkboxes */}
                  <div className="col-md-8">
                    <label className="form-label small fw-semibold text-muted text-uppercase">
                      Playlists
                    </label>
                    <div className="border rounded" style={{ minHeight: 80 }}>
                      {browseAccountId ? (
                        fromLoading ? (
                          <div className="text-center py-4 text-muted">
                            <span className="spinner-border spinner-border-sm me-2" />Loading playlists…
                          </div>
                        ) : !currentPlaylists?.length ? (
                          <p className="text-muted small text-center py-3 mb-0">No playlists found for this account.</p>
                        ) : (
                          <div className="list-group list-group-flush" style={{ maxHeight: 360, overflowY: 'auto' }}>
                            {currentPlaylists.map((pl) => {
                              const checked = isSelected(browseAccountId, pl.id)
                              return (
                                <label
                                  key={pl.id}
                                  className={`list-group-item list-group-item-action d-flex align-items-center gap-3 ${
                                    checked ? 'bg-primary-subtle' : ''
                                  }`}
                                  style={{ cursor: 'pointer' }}
                                >
                                  <input
                                    type="checkbox"
                                    className="form-check-input flex-shrink-0 m-0"
                                    checked={checked}
                                    onChange={() => togglePlaylist(pl)}
                                  />
                                  <span className="flex-grow-1 d-flex justify-content-between align-items-center">
                                    <span>
                                      <i className="bi bi-collection-play me-2 text-warning"></i>
                                      {pl.name}
                                    </span>
                                    <span className="badge bg-secondary-subtle text-secondary border border-secondary-subtle rounded-pill">
                                      {pl.track_count ?? '?'} tracks
                                    </span>
                                  </span>
                                </label>
                              )
                            })}
                          </div>
                        )
                      ) : (
                        <div className="text-center py-4 text-muted">
                          <i className="bi bi-hand-index-thumb me-2"></i>
                          Select an account on the left to browse its playlists.
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Selected playlists pills */}
                {selectedPlaylists.length > 0 && (
                  <div className="mt-3 p-3 bg-body-tertiary rounded border">
                    <div className="d-flex align-items-center justify-content-between mb-2">
                      <span className="small fw-semibold text-muted">
                        <i className="bi bi-check-circle me-1 text-success"></i>
                        {selectedPlaylists.length} playlist{selectedPlaylists.length !== 1 ? 's' : ''} selected
                      </span>
                    </div>
                    <div className="d-flex flex-wrap gap-2">
                      {selectedPlaylists.map((p) => {
                        const src = sources.find((s) => s.id === p.source_id)
                        const meta = src
                          ? sourceMeta(src.source_type)
                          : { label: 'Source', icon: 'bi-plug', color: 'text-muted' }
                        return (
                          <span
                            key={plKey(p)}
                            className="badge rounded-pill bg-light border d-flex align-items-center gap-1 py-2 px-3"
                          >
                            <i className={`bi ${meta.icon} ${meta.color}`}></i>
                            <span className="small">{meta.label} · {p.playlist_name}</span>
                            <button
                              type="button"
                              className="btn btn-sm btn-link p-0 ms-1 text-muted"
                              onClick={() => removePlaylist(p.source_id, p.playlist_id)}
                            >
                              <i className="bi bi-x-lg" style={{ fontSize: '0.7rem' }}></i>
                            </button>
                          </span>
                        )
                      })}
                    </div>
                  </div>
                )}

                {/* Next button */}
                <div className="d-flex justify-content-end mt-3">
                  <button
                    className="btn btn-primary"
                    disabled={selectedPlaylists.length === 0}
                    onClick={() => setWizardStep(2)}
                  >
                    Configure Roles
                    <i className="bi bi-arrow-right ms-2"></i>
                  </button>
                </div>
              </div>
            )}

            {/* ── STEP 2: Configure Roles ── */}
            {wizardStep === 2 && (
              <div>
                <div className="d-flex align-items-center justify-content-between mb-3">
                  <p className="text-muted small mb-0">
                    For each playlist, choose whether it should act as a <strong>Source</strong> (read tracks from),
                    a <strong>Destination</strong> (sync tracks to), or <strong>Bidirectional</strong> (both).
                  </p>
                  {/* Quick-assign buttons */}
                  <div className="d-flex gap-1 flex-shrink-0 ms-3">
                    <span className="small text-muted me-1 align-self-center">Set all:</span>
                    {ROLE_OPTIONS.map((opt) => (
                      <button
                        key={opt.value}
                        type="button"
                        className="btn btn-sm btn-outline-secondary"
                        onClick={() => setAllRoles(opt.value)}
                        title={`Set all playlists as ${opt.label}`}
                      >
                        <i className={`bi ${opt.icon} me-1`}></i>
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="border rounded overflow-hidden">
                  <table className="table table-sm table-hover align-middle mb-0">
                    <thead className="table-light">
                      <tr>
                        <th className="ps-3">Platform</th>
                        <th>Playlist</th>
                        <th className="text-end pe-3" style={{ width: 320 }}>Role</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedPlaylists.map((p) => {
                        const src = sources.find((s) => s.id === p.source_id)
                        const meta = src
                          ? sourceMeta(src.source_type)
                          : { label: 'Source', icon: 'bi-plug', color: 'text-muted' }
                        const roleOpt = ROLE_OPTIONS.find((r) => r.value === p.role)
                        return (
                          <tr key={plKey(p)}>
                            <td className="ps-3">
                              <span className={`${meta.color}`}>
                                <i className={`bi ${meta.icon} me-2`}></i>
                                <span className="fw-semibold small">{src?.name || meta.label}</span>
                              </span>
                            </td>
                            <td>
                              <div className="d-flex align-items-center gap-2">
                                <i className="bi bi-collection-play text-warning"></i>
                                <span className="small">{p.playlist_name}</span>
                              </div>
                            </td>
                            <td className="text-end pe-3">
                              <div className="d-flex align-items-center justify-content-end gap-2">
                                <RoleSelector
                                  role={p.role}
                                  onChange={(r) => setPlaylistRole(p.source_id, p.playlist_id, r)}
                                />
                                <button
                                  type="button"
                                  className="btn btn-sm btn-link text-danger p-0"
                                  title="Remove from sync"
                                  onClick={() => removePlaylist(p.source_id, p.playlist_id)}
                                >
                                  <i className="bi bi-trash"></i>
                                </button>
                              </div>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Validation messages */}
                {selectedPlaylists.length > 0 && !canStart && (
                  <div className="alert alert-warning mt-3 py-2 small mb-0">
                    <i className="bi bi-exclamation-triangle me-2"></i>
                    You need at least one <strong>Source</strong> (or Bidirectional) and one <strong>Destination</strong> (or Bidirectional) to start a sync.
                  </div>
                )}

                {/* Summary + actions */}
                <div className="border-top pt-3 mt-3 d-flex align-items-center justify-content-between">
                  <div className="d-flex align-items-center gap-3">
                    <button
                      className="btn btn-outline-secondary btn-sm"
                      onClick={() => setWizardStep(1)}
                    >
                      <i className="bi bi-arrow-left me-1"></i>Back
                    </button>
                    <div className="small text-muted">
                      <span className="me-3">
                        <i className="bi bi-box-arrow-right me-1 text-info"></i>
                        <strong>{srcCount}</strong> source{srcCount !== 1 ? 's' : ''}
                      </span>
                      <span>
                        <i className="bi bi-box-arrow-in-right me-1 text-warning"></i>
                        <strong>{dstCount}</strong> destination{dstCount !== 1 ? 's' : ''}
                      </span>
                    </div>
                  </div>
                  <button
                    className="btn btn-danger"
                    disabled={jobLoading || !canStart}
                    onClick={handleStartSync}
                  >
                    {jobLoading ? (
                      <>
                        <span className="spinner-border spinner-border-sm me-1" />
                        Starting…
                      </>
                    ) : (
                      <>
                        <i className="bi bi-play-fill me-1"></i>
                        Start Sync
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── Active Job View ── */}
        {job && (
          <div className="card shadow-sm">
            <div className="card-header d-flex align-items-center justify-content-between">
              <span className="fw-semibold">
                <i className="bi bi-arrow-repeat me-2 text-primary"></i>
                {job.playlist_name}
                {job.source_from && job.source_to && (
                  <span className="ms-2 small fw-normal text-muted">
                    <i className={`bi ${sourceMeta(job.source_from.source_type).icon} ${sourceMeta(job.source_from.source_type).color} me-1`}></i>
                    {job.source_from.name}
                    <i className="bi bi-arrow-right mx-2"></i>
                    <i className={`bi ${sourceMeta(job.source_to.source_type).icon} ${sourceMeta(job.source_to.source_type).color} me-1`}></i>
                    {job.source_to.name}
                  </span>
                )}
              </span>
              <div className="d-flex align-items-center gap-2">
                {POLLING_STATUSES.has(job.status) && (
                  <span className="spinner-border spinner-border-sm text-info" />
                )}
                <span className={`badge ${jobBadge.cls}`}>{jobBadge.label}</span>
                <a
                  href={`/api/sync/${job.id}/export/`}
                  className="btn btn-sm btn-outline-secondary"
                  download
                  title="Export results as Excel"
                >
                  <i className="bi bi-file-earmark-excel me-1"></i>Export
                </a>
              </div>
            </div>

            <div className="card-body pb-0">
              {job.status === 'failed' && job.error_message && (
                <div className="alert alert-danger mb-3" role="alert">
                  <i className="bi bi-exclamation-triangle me-2"></i>
                  {job.error_message}
                </div>
              )}
              <JobProgress job={job} />
              {!isMultiDestinationJob && unconfirmedMatchCount > 0 && (
                <div className="d-flex justify-content-end mb-2">
                  <button
                    className="btn btn-sm btn-success"
                    onClick={() => dispatch(confirmAllTracks(job.id))}
                  >
                    <i className="bi bi-check-all me-1"></i>
                    Validate All ({unconfirmedMatchCount})
                  </button>
                </div>
              )}
            </div>

            {tracks.length > 0 && !isMultiDestinationJob && (
              <div className="table-responsive">
                <table className="table table-sm table-hover align-middle mb-0">
                  <thead className="table-light">
                    <tr>
                      <th style={{ width: 44 }}></th>
                      <th>Track</th>
                      <th style={{ width: 60 }}>Duration</th>
                      <th style={{ width: 100 }}>Status</th>
                      <th style={{ width: 60 }}>Conf.</th>
                      <th>{matchColHeader}</th>
                      <th style={{ width: 140 }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {tracks.map((track) => (
                      <TrackRow
                        key={track.id}
                        track={track}
                        jobId={job.id}
                        sourceType={job.source_from?.source_type}
                        targetType={targetType}
                        dispatch={dispatch}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {tracks.length > 0 && isMultiDestinationJob && (
              <div className="table-responsive">
                <table className="table table-sm table-hover align-middle mb-0">
                  <thead className="table-light">
                    <tr>
                      <th style={{ width: 44 }}></th>
                      <th>Track</th>
                      <th style={{ width: 60 }}>Duration</th>
                      {destinationPlaylists.map((dest) => {
                        const meta = sourceMeta(dest.source.source_type)
                        return (
                          <th key={dest.id} className="text-center">
                            <div className="d-flex flex-column align-items-center">
                              <span className="small fw-semibold">
                                <i className={`bi ${meta.icon} ${meta.color} me-1`}></i>
                                {dest.source.name}
                              </span>
                              {dest.playlist_name && (
                                <span className="text-muted small text-truncate" style={{ maxWidth: 160 }}>
                                  {dest.playlist_name}
                                </span>
                              )}
                            </div>
                          </th>
                        )
                      })}
                    </tr>
                  </thead>
                  <tbody>
                    {tracks.map((track) => (
                      <MultiDestinationTrackRow
                        key={track.id}
                        track={track}
                        jobId={job.id}
                        sourceType={job.source_from?.source_type}
                        destinations={destinationPlaylists}
                        dispatch={dispatch}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {tracks.length === 0 && job.status === 'analyzing' && (
              <div className="card-body text-center text-muted py-4">
                <span className="spinner-border spinner-border-sm me-2" />
                Fetching tracks and searching {targetMeta?.label ?? 'target'}…
              </div>
            )}

            {/* ── Push to Playlist panel ── */}
            {(job.status === 'ready' || job.status === 'done') && (
              <PushToPlaylist
                job={job}
                targetPlaylists={targetPlaylists}
                targetPlaylistsLoading={playlistsLoading}
                dispatch={dispatch}
              />
            )}
          </div>
        )}

      </div>
    </div>
  )
}
