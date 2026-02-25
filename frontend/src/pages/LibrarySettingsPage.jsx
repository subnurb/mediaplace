import React, { useEffect, useRef, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { fetchPlaylists } from '../store/syncSlice'
import {
  addLibraryPlaylist,
  fetchLibrarySettings,
  removeLibraryPlaylist,
  stopLibrarySync,
  syncLibraryPlaylist,
} from '../store/librarySlice'
import { setActiveTool } from '../store/uiSlice'

// ── Helpers ───────────────────────────────────────────────────────────────────

const SOURCE_META = {
  youtube_publish: { label: 'YouTube',    icon: 'bi-youtube',           color: 'text-danger'   },
  soundcloud:      { label: 'SoundCloud', icon: 'bi-soundwave',         color: 'text-warning'  },
  spotify:         { label: 'Spotify',    icon: 'bi-music-note-beamed', color: 'text-success'  },
  deezer:          { label: 'Deezer',     icon: 'bi-music-player',      color: 'text-primary'  },
  local:           { label: 'Local',      icon: 'bi-folder',            color: 'text-secondary'},
  ftp:             { label: 'FTP',        icon: 'bi-server',            color: 'text-secondary'},
}

function sourceMeta(type) {
  return SOURCE_META[type] || { label: type, icon: 'bi-plug', color: 'text-muted' }
}

function fmtTime(iso) {
  if (!iso) return null
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now - d
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin} min ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  return d.toLocaleDateString()
}

// ── SourceSelect ──────────────────────────────────────────────────────────────

function SourceSelect({ sources, value, onChange }) {
  return (
    <select
      className="form-select form-select-sm"
      value={value ?? ''}
      onChange={e => onChange(e.target.value ? Number(e.target.value) : null)}
      style={{ minWidth: 180 }}
    >
      <option value="">— choose account —</option>
      {sources.map(s => {
        const meta = sourceMeta(s.source_type)
        return (
          <option key={s.id} value={s.id}>
            {meta.label} · {s.name}
          </option>
        )
      })}
    </select>
  )
}

// ── PlaylistBrowser ───────────────────────────────────────────────────────────

function PlaylistBrowser({ playlists, loading, alreadyTracked, onSelect }) {
  if (loading) {
    return (
      <div className="text-center py-3 text-muted">
        <span className="spinner-border spinner-border-sm me-2" />Loading playlists…
      </div>
    )
  }
  if (!playlists?.length) {
    return <p className="text-muted small text-center py-3 mb-0">No playlists found for this account.</p>
  }

  return (
    <div className="list-group list-group-flush" style={{ maxHeight: 260, overflowY: 'auto' }}>
      {playlists.map(pl => {
        const tracked = alreadyTracked.has(pl.id)
        return (
          <button
            key={pl.id}
            className={`list-group-item list-group-item-action d-flex justify-content-between align-items-center ${tracked ? 'disabled' : ''}`}
            onClick={() => !tracked && onSelect(pl)}
          >
            <span>
              <i className="bi bi-collection-play me-2 text-warning"></i>
              {pl.name}
            </span>
            <div className="d-flex align-items-center gap-2">
              <span className="badge bg-secondary-subtle text-secondary border border-secondary-subtle rounded-pill">
                {pl.track_count ?? '?'} tracks
              </span>
              {tracked && (
                <span className="badge bg-success-subtle text-success border border-success-subtle rounded-pill">
                  Added
                </span>
              )}
            </div>
          </button>
        )
      })}
    </div>
  )
}

// ── Tracked playlist row ──────────────────────────────────────────────────────

const PHASE_LABEL = {
  importing:       'Importing tracks',
  fingerprinting:  'Analyzing audio',
}

function TrackedPlaylistRow({ lp, onSync, onStop, onRemove }) {
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [stopping, setStopping] = useState(false)
  const meta = sourceMeta(lp.source?.source_type)

  async function handleStop() {
    setStopping(true)
    await onStop(lp.id)
    setStopping(false)
  }

  return (
    <div className="card mb-2 border-0 shadow-sm">
      <div className="card-body py-2 px-3">
        <div className="d-flex align-items-center justify-content-between flex-wrap gap-2">
          <div className="d-flex align-items-center gap-2 flex-grow-1 min-width-0">
            {/* Platform icon */}
            <i className={`bi ${meta.icon} ${meta.color} fs-5`}></i>

            <div className="min-width-0" style={{ flex: 1 }}>
              <div className="fw-semibold text-truncate">{lp.playlist_name}</div>
              <div className="small text-muted">
                <span>{lp.source?.name}</span>
                <span className="mx-1">·</span>
                <span>{lp.track_count} tracks</span>
                {lp.last_synced_at && (
                  <>
                    <span className="mx-1">·</span>
                    <span>Last synced {fmtTime(lp.last_synced_at)}</span>
                  </>
                )}
              </div>

              {/* Progress bar — visible while syncing */}
              {lp.syncing && (
                <div className="mt-2">
                  <div className="d-flex justify-content-between align-items-center mb-1">
                    <span className="small text-muted">
                      {PHASE_LABEL[lp.sync_phase] || 'Syncing'}…
                    </span>
                    <span className="small text-muted fw-semibold">{lp.sync_progress}%</span>
                  </div>
                  <div className="progress" style={{ height: 6 }}>
                    <div
                      className="progress-bar progress-bar-striped progress-bar-animated bg-info"
                      style={{ width: `${lp.sync_progress}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="d-flex align-items-center gap-2 flex-shrink-0">
            {lp.syncing ? (
              <button
                className="btn btn-sm btn-outline-warning"
                onClick={handleStop}
                disabled={stopping}
                title="Stop sync"
              >
                {stopping
                  ? <span className="spinner-border spinner-border-sm" style={{ width: '0.75rem', height: '0.75rem' }} />
                  : <i className="bi bi-stop-circle"></i>
                }
              </button>
            ) : (
              <button
                className="btn btn-sm btn-outline-secondary"
                onClick={() => onSync(lp.id)}
                title="Re-sync"
              >
                <i className="bi bi-arrow-clockwise"></i>
              </button>
            )}

            {confirmDelete ? (
              <div className="d-flex gap-1">
                <button className="btn btn-sm btn-danger" onClick={() => onRemove(lp.id)}>
                  Remove
                </button>
                <button className="btn btn-sm btn-outline-secondary" onClick={() => setConfirmDelete(false)}>
                  Cancel
                </button>
              </div>
            ) : (
              <button
                className="btn btn-sm btn-outline-danger"
                onClick={() => setConfirmDelete(true)}
                title="Remove from library"
              >
                <i className="bi bi-x-lg"></i>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function LibrarySettingsPage() {
  const dispatch = useDispatch()
  const { items: sources } = useSelector(s => s.sources)
  const playlists = useSelector(s => s.sync.playlists)
  const playlistsLoading = useSelector(s => s.sync.playlistsLoading)
  const { trackedPlaylists, settingsLoading, error } = useSelector(s => s.library)

  const [selectedSourceId, setSelectedSourceId] = useState(null)
  const [adding, setAdding] = useState(false)
  const pollRef = useRef(null)

  useEffect(() => {
    dispatch(setActiveTool('library-settings'))
    dispatch(fetchLibrarySettings())
  }, [dispatch])

  // Load playlists when source changes
  useEffect(() => {
    if (selectedSourceId) {
      dispatch(fetchPlaylists(selectedSourceId))
    }
  }, [selectedSourceId, dispatch])

  // Poll while any playlist is syncing
  useEffect(() => {
    const anySyncing = trackedPlaylists.some(p => p.syncing)

    if (anySyncing && !pollRef.current) {
      pollRef.current = setInterval(() => {
        dispatch(fetchLibrarySettings())
      }, 3000)
    }

    if (!anySyncing && pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
  }, [trackedPlaylists, dispatch])

  // Build set of already-tracked playlist IDs for the selected source
  const alreadyTrackedIds = new Set(
    trackedPlaylists
      .filter(p => p.source?.id === selectedSourceId)
      .map(p => p.playlist_id)
  )

  const currentPlaylists = selectedSourceId ? (playlists[selectedSourceId] || []) : []
  const isLoadingPlaylists = selectedSourceId && playlistsLoading

  async function handleSelectPlaylist(pl) {
    if (!selectedSourceId) return
    setAdding(true)
    try {
      await dispatch(addLibraryPlaylist({
        sourceId: selectedSourceId,
        playlistId: pl.id,
        playlistName: pl.name,
      })).unwrap()
    } catch (e) {
      // error shown from Redux state
    } finally {
      setAdding(false)
    }
  }

  function handleSync(id) {
    dispatch(syncLibraryPlaylist(id))
  }

  async function handleStop(id) {
    await dispatch(stopLibrarySync(id))
  }

  function handleRemove(id) {
    dispatch(removeLibraryPlaylist(id))
  }

  return (
    <div className="container-fluid py-3" style={{ maxWidth: 780 }}>
      <h5 className="fw-semibold mb-1">Library Settings</h5>
      <p className="text-muted small mb-4">
        Select playlists to track. Tracks are imported and fingerprinted in the background (BPM, key, mode via AcoustID).
      </p>

      {error && (
        <div className="alert alert-danger alert-dismissible">
          {error}
          <button type="button" className="btn-close" onClick={() => dispatch({ type: 'library/clearLibraryError' })}></button>
        </div>
      )}

      {/* ── Add playlist panel ──────────────────────────────────────────── */}
      <div className="card border-0 shadow-sm mb-4">
        <div className="card-header bg-white border-bottom py-2 px-3">
          <span className="fw-semibold small text-uppercase text-muted">Add Playlist</span>
        </div>
        <div className="card-body p-3">
          <div className="mb-3">
            <label className="form-label small fw-semibold text-muted text-uppercase mb-1">Account</label>
            <SourceSelect
              sources={sources}
              value={selectedSourceId}
              onChange={setSelectedSourceId}
            />
          </div>

          {selectedSourceId && (
            <>
              <label className="form-label small fw-semibold text-muted text-uppercase mb-1">Playlist</label>
              {adding && (
                <div className="text-center py-2 text-muted small">
                  <span className="spinner-border spinner-border-sm me-2" />Adding…
                </div>
              )}
              <PlaylistBrowser
                playlists={currentPlaylists}
                loading={isLoadingPlaylists}
                alreadyTracked={alreadyTrackedIds}
                onSelect={handleSelectPlaylist}
              />
            </>
          )}

          {!selectedSourceId && (
            <p className="text-muted small mb-0">Select an account above to browse its playlists.</p>
          )}
        </div>
      </div>

      {/* ── Tracked playlists ──────────────────────────────────────────── */}
      <div className="mb-2 d-flex align-items-center justify-content-between">
        <span className="fw-semibold small text-uppercase text-muted">Tracked Playlists</span>
        {settingsLoading && <span className="spinner-border spinner-border-sm text-muted" role="status"></span>}
      </div>

      {trackedPlaylists.length === 0 && !settingsLoading ? (
        <div className="text-center py-4 text-muted border rounded">
          <i className="bi bi-music-note-list fs-3 mb-2 d-block"></i>
          No playlists tracked yet. Add one above.
        </div>
      ) : (
        trackedPlaylists.map(lp => (
          <TrackedPlaylistRow
            key={lp.id}
            lp={lp}
            onSync={handleSync}
            onStop={handleStop}
            onRemove={handleRemove}
          />
        ))
      )}
    </div>
  )
}
