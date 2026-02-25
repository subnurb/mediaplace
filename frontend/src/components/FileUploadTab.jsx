import React, { useRef, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { uploadFiles } from '../store/jobSlice'
import ChannelSelect from './ChannelSelect'

export default function FileUploadTab() {
  const dispatch = useDispatch()
  const { loading } = useSelector((s) => s.job)
  const formRef = useRef()
  const [audioName, setAudioName] = useState('')
  const [imageName, setImageName] = useState('')
  const [sourceId, setSourceId] = useState(null)

  const handleSubmit = (e) => {
    e.preventDefault()
    const fd = new FormData(formRef.current)
    if (sourceId) fd.append('source_id', sourceId)
    dispatch(uploadFiles(fd))
  }

  return (
    <form ref={formRef} onSubmit={handleSubmit}>
      <div className="row g-3">

        <div className="col-md-6">
          <label className="form-label fw-semibold">Audio File <span className="text-danger">*</span></label>
          <input
            type="file"
            name="audio"
            accept="audio/*"
            required
            className="form-control"
            onChange={(e) => setAudioName(e.target.files[0]?.name || '')}
          />
          {audioName && <div className="form-text text-truncate">{audioName}</div>}
        </div>

        <div className="col-md-6">
          <label className="form-label fw-semibold">Cover Image <span className="text-danger">*</span></label>
          <input
            type="file"
            name="image"
            accept="image/*"
            required
            className="form-control"
            onChange={(e) => setImageName(e.target.files[0]?.name || '')}
          />
          {imageName && <div className="form-text text-truncate">{imageName}</div>}
        </div>

        <div className="col-12">
          <label className="form-label fw-semibold">Video Title <span className="text-danger">*</span></label>
          <input
            type="text"
            name="title"
            placeholder="My awesome track"
            required
            className="form-control"
          />
        </div>

        <div className="col-12">
          <label className="form-label fw-semibold">Description</label>
          <textarea
            name="description"
            rows={3}
            placeholder="Description of your video…"
            className="form-control"
          />
        </div>

        <div className="col-md-6">
          <label className="form-label fw-semibold">Tags <span className="text-muted fw-normal">(comma-separated)</span></label>
          <input
            type="text"
            name="tags"
            placeholder="music, lofi, chill"
            className="form-control"
          />
        </div>

        <div className="col-md-3">
          <label className="form-label fw-semibold">Animation</label>
          <select name="animation" className="form-select">
            <option value="none">Static image</option>
            <option value="circle_pulse">Circle & Pulse</option>
          </select>
        </div>

        <div className="col-md-3">
          <label className="form-label fw-semibold">Privacy</label>
          <select name="privacy" className="form-select">
            <option value="unlisted">Unlisted</option>
            <option value="public">Public</option>
            <option value="private">Private</option>
          </select>
        </div>

        <div className="col-12">
          <hr className="my-1" />
          <label className="form-label fw-semibold">Publish to YouTube channel</label>
          <ChannelSelect value={sourceId} onChange={setSourceId} />
          <div className="form-text">Leave empty to only download the video.</div>
        </div>

        <div className="col-12">
          <button type="submit" className="btn btn-danger w-100" disabled={loading}>
            {loading ? (
              <><span className="spinner-border spinner-border-sm me-2" />Processing… this may take a few minutes</>
            ) : (
              <><i className="bi bi-film me-2"></i>Create Video</>
            )}
          </button>
        </div>

      </div>
    </form>
  )
}
