import React, { useEffect, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { fetchSyncLog, loadJob } from '../store/syncSlice'
import { setActiveTool } from '../store/uiSlice'

// ── Helpers ───────────────────────────────────────────────────────────────────

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

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function confLabel(confidence) {
  if (confidence === null || confidence === undefined) return ''
  const pct = Math.round(confidence * 100)
  const cls = confidence >= 0.90 ? 'text-success' : confidence >= 0.55 ? 'text-warning' : 'text-danger'
  return <span className={`small fw-semibold ${cls}`}>{pct}%</span>
}

const JOB_STATUS_BADGE = {
  pending:   { cls: 'bg-secondary',          label: 'Pending'    },
  analyzing: { cls: 'bg-info',               label: 'Analyzing'  },
  ready:     { cls: 'bg-primary',            label: 'Ready'      },
  syncing:   { cls: 'bg-warning text-dark',  label: 'Syncing…'   },
  done:      { cls: 'bg-success',            label: 'Done'       },
  failed:    { cls: 'bg-danger',             label: 'Failed'     },
}

const TRACK_STATUS_BADGE = {
  matched:   { cls: 'bg-success-subtle text-success border border-success-subtle',    label: 'Matched'   },
  uncertain: { cls: 'bg-warning-subtle text-warning border border-warning-subtle',    label: 'Uncertain' },
  not_found: { cls: 'bg-danger-subtle text-danger border border-danger-subtle',       label: 'Not Found' },
  uploaded:  { cls: 'bg-success-subtle text-success border border-success-subtle',    label: 'Uploaded'  },
  failed:    { cls: 'bg-danger-subtle text-danger border border-danger-subtle',       label: 'Failed'    },
  skipped:   { cls: 'bg-light text-muted border',                                     label: 'Skipped'   },
  pending:   { cls: 'bg-secondary-subtle text-secondary border border-secondary-subtle', label: 'Pending' },
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatsBadges({ stats }) {
  if (!stats) return null
  return (
    <div className="d-flex flex-wrap gap-2 mt-2">
      {stats.matched > 0 && (
        <span className="badge rounded-pill bg-success-subtle text-success border border-success-subtle" style={{ fontSize: '0.72rem' }}>
          <i className="bi bi-check-circle me-1"></i>{stats.matched} matched
        </span>
      )}
      {stats.uploaded > 0 && (
        <span className="badge rounded-pill bg-success-subtle text-success border border-success-subtle" style={{ fontSize: '0.72rem' }}>
          <i className="bi bi-cloud-upload me-1"></i>{stats.uploaded} uploaded
        </span>
      )}
      {stats.uncertain > 0 && (
        <span className="badge rounded-pill bg-warning-subtle text-warning border border-warning-subtle" style={{ fontSize: '0.72rem' }}>
          <i className="bi bi-question-circle me-1"></i>{stats.uncertain} uncertain
        </span>
      )}
      {stats.not_found > 0 && (
        <span className="badge rounded-pill bg-danger-subtle text-danger border border-danger-subtle" style={{ fontSize: '0.72rem' }}>
          <i className="bi bi-x-circle me-1"></i>{stats.not_found} not found
        </span>
      )}
      {stats.skipped > 0 && (
        <span className="badge rounded-pill bg-light text-muted border" style={{ fontSize: '0.72rem' }}>
          {stats.skipped} skipped
        </span>
      )}
      {stats.pushed > 0 && (
        <span className="badge rounded-pill bg-primary-subtle text-primary border border-primary-subtle" style={{ fontSize: '0.72rem' }}>
          <i className="bi bi-send me-1"></i>{stats.pushed} pushed
        </span>
      )}
    </div>
  )
}

function UnsyncedTrackList({ tracks }) {
  if (!tracks?.length) return null
  return (
    <div className="mt-3">
      <h6 className="small fw-semibold text-muted text-uppercase mb-2">
        <i className="bi bi-exclamation-triangle me-1 text-warning"></i>
        {tracks.length} unsynced track{tracks.length !== 1 ? 's' : ''} needing attention
      </h6>
      <div className="list-group list-group-flush rounded border">
        {tracks.map((t) => {
          const badge = TRACK_STATUS_BADGE[t.status] || TRACK_STATUS_BADGE.pending
          return (
            <div
              key={t.id}
              className="list-group-item py-2 d-flex align-items-center justify-content-between gap-2"
            >
              <div className="d-flex flex-column">
                <span className="small fw-semibold">{t.source_title}</span>
                {t.source_artist && (
                  <span className="text-muted" style={{ fontSize: '0.78rem' }}>{t.source_artist}</span>
                )}
              </div>
              <div className="d-flex align-items-center gap-2 flex-shrink-0">
                {t.match_confidence != null && confLabel(t.match_confidence)}
                <span className={`badge rounded-pill ${badge.cls}`} style={{ fontSize: '0.68rem' }}>
                  {badge.label}
                </span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function JobCard({ job, onResume }) {
  const [expanded, setExpanded] = useState(false)
  const statusBadge = JOB_STATUS_BADGE[job.status] || JOB_STATUS_BADGE.pending
  const fromMeta = sourceMeta(job.source_from?.source_type)
  const toMeta   = sourceMeta(job.source_to?.source_type)
  const hasUnsynced = job.unsynced_tracks?.length > 0
  const needsAttention = hasUnsynced || ['ready', 'pending', 'failed'].includes(job.status)

  return (
    <div className={`card shadow-sm mb-3 ${needsAttention ? 'border-warning' : ''}`}>
      <div className="card-header d-flex align-items-start justify-content-between gap-2 flex-wrap">
        <div className="flex-grow-1 min-width-0">
          <div className="d-flex align-items-center gap-2 flex-wrap">
            <span className="fw-semibold text-truncate">{job.playlist_name}</span>
            <span className={`badge ${statusBadge.cls}`} style={{ fontSize: '0.72rem' }}>{statusBadge.label}</span>
            {needsAttention && !['done', 'syncing'].includes(job.status) && (
              <span className="badge bg-warning-subtle text-warning border border-warning-subtle" style={{ fontSize: '0.68rem' }}>
                <i className="bi bi-exclamation-triangle me-1"></i>Needs attention
              </span>
            )}
          </div>
          <div className="small text-muted mt-1">
            <i className={`bi ${fromMeta.icon} ${fromMeta.color} me-1`}></i>
            {job.source_from?.name ?? fromMeta.label}
            <i className="bi bi-arrow-right mx-2"></i>
            <i className={`bi ${toMeta.icon} ${toMeta.color} me-1`}></i>
            {job.source_to?.name ?? toMeta.label}
            <span className="ms-3 text-muted">{fmtDate(job.created_at)}</span>
          </div>
        </div>

        <div className="d-flex gap-2 flex-shrink-0">
          <button
            className="btn btn-sm btn-outline-primary"
            onClick={onResume}
            title="Open this sync job"
          >
            <i className="bi bi-arrow-right-circle me-1"></i>Resume
          </button>
          <a
            href={`/api/sync/${job.id}/export/`}
            className="btn btn-sm btn-outline-secondary"
            download
            title="Export results as Excel"
          >
            <i className="bi bi-file-earmark-excel"></i>
          </a>
        </div>
      </div>

      <div className="card-body py-2">
        {/* Status counts */}
        <StatsBadges stats={job.stats} />

        {/* Pushed info */}
        {job.pushed_at && job.target_playlist_name && (
          <div className="mt-2 small text-success">
            <i className="bi bi-check-circle-fill me-1"></i>
            Pushed to <strong>"{job.target_playlist_name}"</strong> · {fmtDate(job.pushed_at)}
          </div>
        )}

        {/* Unsynced tracks toggle */}
        {hasUnsynced && (
          <div className="mt-2">
            <button
              className="btn btn-link btn-sm p-0 text-decoration-none text-warning"
              onClick={() => setExpanded(!expanded)}
            >
              <i className={`bi ${expanded ? 'bi-chevron-up' : 'bi-chevron-down'} me-1`}></i>
              {expanded ? 'Hide' : 'Show'} {job.unsynced_tracks.length} unsynced track{job.unsynced_tracks.length !== 1 ? 's' : ''}
            </button>
            {expanded && <UnsyncedTrackList tracks={job.unsynced_tracks} />}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function SyncLogPage() {
  const dispatch = useDispatch()
  const { syncLog, syncLogLoading, error } = useSelector((s) => s.sync)
  const [filter, setFilter] = useState('all')  // 'all' | 'attention'

  useEffect(() => {
    dispatch(fetchSyncLog())
  }, [dispatch])

  async function handleResume(jobId) {
    const result = await dispatch(loadJob(jobId))
    if (result.meta.requestStatus === 'fulfilled') {
      dispatch(setActiveTool('sync'))
    }
  }

  const filteredJobs = filter === 'attention'
    ? syncLog.filter((j) =>
        j.unsynced_tracks?.length > 0 ||
        ['ready', 'pending', 'failed'].includes(j.status)
      )
    : syncLog

  return (
    <div className="row justify-content-center mt-4">
      <div className="col-xl-10 col-lg-12">

        <div className="d-flex align-items-center justify-content-between mb-3 flex-wrap gap-2">
          <h5 className="fw-semibold mb-0">
            <i className="bi bi-clock-history me-2 text-primary"></i>Sync History
          </h5>
          <div className="btn-group btn-group-sm">
            <button
              className={`btn ${filter === 'all' ? 'btn-primary' : 'btn-outline-secondary'}`}
              onClick={() => setFilter('all')}
            >
              All ({syncLog.length})
            </button>
            <button
              className={`btn ${filter === 'attention' ? 'btn-warning' : 'btn-outline-secondary'}`}
              onClick={() => setFilter('attention')}
            >
              <i className="bi bi-exclamation-triangle me-1"></i>
              Needs attention ({syncLog.filter((j) => j.unsynced_tracks?.length > 0 || ['ready', 'pending', 'failed'].includes(j.status)).length})
            </button>
          </div>
        </div>

        {syncLogLoading && (
          <div className="text-center py-5 text-muted">
            <span className="spinner-border spinner-border-sm me-2" />
            Loading sync history…
          </div>
        )}

        {!syncLogLoading && filteredJobs.length === 0 && (
          <div className="card shadow-sm">
            <div className="card-body text-center py-5 text-muted">
              <i className="bi bi-inbox fs-1 d-block mb-2"></i>
              {filter === 'attention'
                ? 'No sync jobs need attention right now.'
                : 'No sync jobs found. Start your first sync on the Sync Playlists page.'}
            </div>
          </div>
        )}

        {filteredJobs.map((job) => (
          <JobCard
            key={job.id}
            job={job}
            onResume={() => handleResume(job.id)}
          />
        ))}

      </div>
    </div>
  )
}
