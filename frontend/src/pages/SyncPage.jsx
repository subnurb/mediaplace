import React, { useEffect, useRef, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  fetchPlaylists,
  createSyncJob,
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
// or the SoundCloud permalink URL for SC targets.
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
}

function TargetLink({ track, targetType }) {
  if (!track.target_title) {
    return track.status === 'not_found'
      ? <span className="text-muted fst-italic" style={{ fontSize: '0.78rem' }}>No match found</span>
      : null
  }

  const cfg = TARGET_LINK_CONFIG[targetType]
  if (cfg && track.target_video_id) {
    return (
      <a
        href={cfg.href(track.target_video_id)}
        target="_blank"
        rel="noreferrer"
        className="text-decoration-none text-truncate d-inline-block"
        style={{ maxWidth: 200 }}
        title={track.target_title}
      >
        <i className={`bi ${cfg.icon} ${cfg.color} me-1`}></i>
        {track.target_title}
      </a>
    )
  }

  return <span className="text-muted small text-truncate d-inline-block" style={{ maxWidth: 200 }}>{track.target_title}</span>
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
        <TargetLink track={track} targetType={targetType} />
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

function PushToPlaylist({ job, targetPlaylists, targetPlaylistsLoading, dispatch }) {
  const [mode, setMode] = useState('existing')  // 'existing' | 'new'
  const [selectedId, setSelectedId] = useState('')
  const [newName, setNewName] = useState('')
  const { pushLoading } = useSelector((s) => s.sync)

  const tracks = job.tracks || []
  const eligibleTracks = tracks.filter(
    (t) =>
      t.target_video_id &&
      (
        t.status === 'matched' ||
        t.status === 'uploaded' ||
        (t.status === 'uncertain' && t.user_feedback === 'confirmed')
      )
  )

  const pushedCount = tracks.filter((t) => t.pushed_to_playlist).length

  function handlePush() {
    const payload = {
      jobId: job.id,
      targetPlaylistId: mode === 'existing' ? selectedId : null,
      newPlaylistName: mode === 'new' ? newName.trim() : '',
    }
    dispatch(pushToPlaylist(payload))
  }

  const canPush =
    mode === 'existing'
      ? !!selectedId
      : newName.trim().length > 0

  // Success state — job already pushed
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

      {/* Mode toggle */}
      <div className="d-flex gap-3 mb-3">
        <div className="form-check">
          <input
            className="form-check-input"
            type="radio"
            id="modeExisting"
            checked={mode === 'existing'}
            onChange={() => setMode('existing')}
          />
          <label className="form-check-label small" htmlFor="modeExisting">
            Add to existing playlist
          </label>
        </div>
        <div className="form-check">
          <input
            className="form-check-input"
            type="radio"
            id="modeNew"
            checked={mode === 'new'}
            onChange={() => setMode('new')}
          />
          <label className="form-check-label small" htmlFor="modeNew">
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
          disabled={!canPush || pushLoading || eligibleTracks.length === 0}
          onClick={handlePush}
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

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function SyncPage() {
  const dispatch = useDispatch()
  const { items: sources } = useSelector((s) => s.sources)
  const { playlists, playlistsLoading, job, jobLoading, pushLoading, error } = useSelector((s) => s.sync)

  const [fromId, setFromId] = useState(null)
  const [toId, setToId]     = useState(null)
  const [selectedPlaylist, setSelectedPlaylist] = useState(null)

  const pollRef = useRef(null)

  // Load playlists when "from" source changes
  useEffect(() => {
    if (fromId) dispatch(fetchPlaylists(fromId))
  }, [fromId, dispatch])

  // Load target playlists when "to" source changes (needed for push panel)
  useEffect(() => {
    if (toId) dispatch(fetchPlaylists(toId))
  }, [toId, dispatch])

  // Poll while job is running
  useEffect(() => {
    if (job && POLLING_STATUSES.has(job.status)) {
      pollRef.current = setInterval(() => dispatch(pollSyncJob(job.id)), 3000)
    } else {
      clearInterval(pollRef.current)
    }
    return () => clearInterval(pollRef.current)
  }, [job?.id, job?.status, dispatch])

  function handleSelectPlaylist(pl) {
    setSelectedPlaylist(pl)
    dispatch(clearJob())
  }

  async function handleStartSync() {
    if (!fromId || !toId || !selectedPlaylist) return
    const result = await dispatch(createSyncJob({
      sourceFromId: fromId,
      sourceToId: toId,
      playlistId: selectedPlaylist.id,
      playlistName: selectedPlaylist.name,
    }))
    if (result.meta.requestStatus === 'fulfilled') {
      dispatch(analyzeSyncJob(result.payload.id))
    }
  }

  function handleReset() {
    dispatch(clearJob())
    setSelectedPlaylist(null)
  }

  const currentPlaylists = fromId ? (playlists[fromId] || []) : []
  const targetPlaylists  = toId   ? (playlists[toId]   || []) : []
  const jobBadge = job ? (JOB_STATUS_BADGE[job.status] || JOB_STATUS_BADGE.pending) : null
  const tracks = job?.tracks || []
  const targetType = job?.source_to?.source_type || (toId ? sources.find((s) => s.id === toId)?.source_type : null)

  // Count tracks that can still be validated (have a match, not yet confirmed)
  const unconfirmedMatchCount = tracks.filter(
    (t) => ['matched', 'uncertain'].includes(t.status) && t.target_video_id && t.user_feedback !== 'confirmed'
  ).length

  // Column header for match results depends on target platform
  const targetMeta = targetType ? sourceMeta(targetType) : null
  const matchColHeader = targetMeta
    ? <><i className={`bi ${targetMeta.icon} ${targetMeta.color} me-1`}></i>Match on {targetMeta.label}</>
    : 'Match'

  const noSources = sources.length < 2

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

        {/* ── Setup Card ── */}
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
            <div className="row g-3 align-items-start">
              <div className="col-md-5">
                <SourceSelect
                  label="From (source)"
                  sources={sources}
                  excludeId={toId}
                  value={fromId}
                  onChange={(id) => { setFromId(id); setSelectedPlaylist(null); dispatch(clearJob()) }}
                />
              </div>
              <div className="col-md-2 text-center pt-4 mt-1">
                <i className="bi bi-arrow-right fs-4 text-muted"></i>
              </div>
              <div className="col-md-5">
                <SourceSelect
                  label="To (destination)"
                  sources={sources}
                  excludeId={fromId}
                  value={toId}
                  onChange={(id) => setToId(id)}
                />
              </div>
            </div>
          </div>
        </div>

        {/* ── Playlist Browser ── */}
        {fromId && toId && !job && (
          <div className="card shadow-sm mb-3">
            <div className="card-header fw-semibold">
              <i className="bi bi-collection-play me-2 text-warning"></i>
              Select a Playlist
            </div>

            {selectedPlaylist && (
              <div className="card-header bg-primary-subtle d-flex align-items-center justify-content-between border-top-0">
                <span className="fw-semibold text-primary">
                  <i className="bi bi-check-circle me-2"></i>
                  {selectedPlaylist.name}
                  <span className="text-muted fw-normal ms-2 small">
                    ({selectedPlaylist.track_count ?? '?'} tracks)
                  </span>
                </span>
                <button
                  className="btn btn-danger btn-sm"
                  disabled={jobLoading}
                  onClick={handleStartSync}
                >
                  {jobLoading
                    ? <><span className="spinner-border spinner-border-sm me-1" />Starting…</>
                    : <><i className="bi bi-play-fill me-1"></i>Start Sync</>
                  }
                </button>
              </div>
            )}

            <div className="card-body p-0">
              <PlaylistBrowser
                playlists={currentPlaylists}
                loading={playlistsLoading}
                onSelect={handleSelectPlaylist}
              />
            </div>
          </div>
        )}

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
              <JobProgress job={job} />
              {unconfirmedMatchCount > 0 && (
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

            {tracks.length > 0 && (
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
