import React, { useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { uploadFromUrl } from '../store/jobSlice'
import ChannelSelect from './ChannelSelect'

export default function UrlUploadTab() {
  const dispatch = useDispatch()
  const { loading } = useSelector((s) => s.job)

  const [form, setForm] = useState({
    music_url: '',
    title: '',
    description: '',
    tags: '',
    animation: 'none',
    privacy: 'unlisted',
    source_id: null,
  })

  const set = (field) => (e) => setForm((prev) => ({ ...prev, [field]: e.target.value }))

  const handleSubmit = (e) => {
    e.preventDefault()
    dispatch(uploadFromUrl(form))
  }

  return (
    <form onSubmit={handleSubmit}>
      <div className="row g-3">

        <div className="col-12">
          <label className="form-label fw-semibold">Music URL <span className="text-danger">*</span></label>
          <input
            type="url"
            value={form.music_url}
            onChange={set('music_url')}
            placeholder="https://soundcloud.com/artist/track"
            required
            className="form-control"
          />
          <div className="form-text">Supports SoundCloud, YouTube, and more</div>
        </div>

        <div className="col-12">
          <label className="form-label fw-semibold">
            Video Title <span className="text-muted fw-normal">(leave empty to auto-detect)</span>
          </label>
          <input
            type="text"
            value={form.title}
            onChange={set('title')}
            placeholder="Auto-detected from URL"
            className="form-control"
          />
        </div>

        <div className="col-12">
          <label className="form-label fw-semibold">Description</label>
          <textarea
            rows={3}
            value={form.description}
            onChange={set('description')}
            placeholder="Description of your video…"
            className="form-control"
          />
        </div>

        <div className="col-md-6">
          <label className="form-label fw-semibold">Tags <span className="text-muted fw-normal">(comma-separated)</span></label>
          <input
            type="text"
            value={form.tags}
            onChange={set('tags')}
            placeholder="music, lofi, chill"
            className="form-control"
          />
        </div>

        <div className="col-md-3">
          <label className="form-label fw-semibold">Animation</label>
          <select value={form.animation} onChange={set('animation')} className="form-select">
            <option value="none">Static image</option>
            <option value="circle_pulse">Circle & Pulse</option>
          </select>
        </div>

        <div className="col-md-3">
          <label className="form-label fw-semibold">Privacy</label>
          <select value={form.privacy} onChange={set('privacy')} className="form-select">
            <option value="unlisted">Unlisted</option>
            <option value="public">Public</option>
            <option value="private">Private</option>
          </select>
        </div>

        <div className="col-12">
          <hr className="my-1" />
          <label className="form-label fw-semibold">Publish to YouTube channel</label>
          <ChannelSelect
            value={form.source_id}
            onChange={(id) => setForm((p) => ({ ...p, source_id: id }))}
          />
          <div className="form-text">Leave empty to only download the video.</div>
        </div>

        <div className="col-12">
          <button type="submit" className="btn btn-danger w-100" disabled={loading}>
            {loading ? (
              <><span className="spinner-border spinner-border-sm me-2" />Downloading & processing…</>
            ) : (
              <><i className="bi bi-cloud-download me-2"></i>Download & Create Video</>
            )}
          </button>
        </div>

      </div>
    </form>
  )
}
