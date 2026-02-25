import React from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { connectYouTube } from '../store/sourcesSlice'

/**
 * A YouTube-channel selector placed at the end of upload forms.
 *
 * Props:
 *   value    – currently selected source id (number | null)
 *   onChange – called with (id: number | null) when selection changes
 */
export default function ChannelSelect({ value, onChange }) {
  const dispatch = useDispatch()
  const channels = useSelector((s) =>
    s.sources.items.filter((src) => src.source_type === 'youtube_publish')
  )

  if (channels.length === 0) {
    return (
      <div className="d-flex align-items-center gap-3 py-1">
        <span className="text-muted small">
          <i className="bi bi-youtube text-danger me-1"></i>
          No YouTube channels connected.
        </span>
        <button
          type="button"
          className="btn btn-sm btn-outline-danger"
          onClick={() => dispatch(connectYouTube())}
        >
          <i className="bi bi-plus-lg me-1"></i>Connect a channel
        </button>
      </div>
    )
  }

  return (
    <div className="input-group">
      <span className="input-group-text bg-body-secondary">
        <i className="bi bi-youtube text-danger"></i>
      </span>
      <select
        className="form-select"
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
      >
        <option value="">— Select a channel (optional) —</option>
        {channels.map((ch) => (
          <option key={ch.id} value={ch.id}>
            {ch.name}
          </option>
        ))}
      </select>
    </div>
  )
}
