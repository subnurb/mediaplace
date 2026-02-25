import React from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { publishVideo, clearJobState } from '../store/jobSlice'
import { connectYouTube } from '../store/sourcesSlice'

export default function JobStatus() {
  const dispatch = useDispatch()
  const { videoReady, pendingJob, success, videoId, youtubeSignupRequired, loading, error } =
    useSelector((s) => s.job)
  const sources = useSelector((s) => s.sources.items)

  // Resolve the target channel: prefer the one stored on the job, then the first connected channel
  const targetChannel = pendingJob?.source_id
    ? sources.find((s) => s.id === pendingJob.source_id)
    : sources.find((s) => s.source_type === 'youtube_publish')

  if (!videoReady && !success && !youtubeSignupRequired) return null

  return (
    <div className="mb-4">

      {success && (
        <div className="alert alert-success d-flex align-items-center gap-2" role="alert">
          <i className="bi bi-check-circle-fill fs-5"></i>
          <div>
            Video published!{' '}
            <a
              href={`https://www.youtube.com/watch?v=${videoId}`}
              target="_blank"
              rel="noreferrer"
              className="alert-link"
            >
              Watch on YouTube <i className="bi bi-box-arrow-up-right"></i>
            </a>
          </div>
          <button
            type="button"
            className="btn-close ms-auto"
            onClick={() => dispatch(clearJobState())}
          />
        </div>
      )}

      {youtubeSignupRequired && (
        <div className="alert alert-warning" role="alert">
          <h6 className="alert-heading fw-bold">
            <i className="bi bi-exclamation-triangle me-2"></i>YouTube channel required
          </h6>
          <p className="mb-2">Your Google account does not have a YouTube channel yet.</p>
          <ol className="mb-3">
            <li>Go to <a href="https://www.youtube.com" target="_blank" rel="noreferrer" className="alert-link">youtube.com</a></li>
            <li>Sign in with the same Google account</li>
            <li>Click your profile icon → <strong>Create a channel</strong></li>
            <li>Follow the setup prompts</li>
          </ol>
          <button
            className="btn btn-warning btn-sm"
            disabled={loading}
            onClick={() => dispatch(publishVideo())}
          >
            {loading ? (
              <><span className="spinner-border spinner-border-sm me-1" /> Retrying…</>
            ) : (
              <><i className="bi bi-arrow-clockwise me-1"></i>Retry Upload</>
            )}
          </button>
        </div>
      )}

      {error && (
        <div className="alert alert-danger d-flex align-items-center gap-2" role="alert">
          <i className="bi bi-x-circle-fill"></i>
          <span>{error}</span>
        </div>
      )}

      {videoReady && pendingJob && (
        <div className="card border-success">
          <div className="card-header bg-success text-white d-flex align-items-center gap-2">
            <i className="bi bi-film"></i>
            <span className="fw-semibold">Video ready — "{pendingJob.title}"</span>
          </div>
          <div className="card-body d-flex gap-3 flex-wrap align-items-center">
            <a href="/api/jobs/download/" className="btn btn-success">
              <i className="bi bi-download me-1"></i>Download
            </a>

            {targetChannel ? (
              <button
                className="btn btn-danger"
                disabled={loading}
                onClick={() => dispatch(publishVideo())}
              >
                {loading ? (
                  <><span className="spinner-border spinner-border-sm me-1" /> Publishing…</>
                ) : (
                  <><i className="bi bi-youtube me-1"></i>Publish to {targetChannel.name}</>
                )}
              </button>
            ) : (
              <button
                className="btn btn-outline-danger"
                type="button"
                onClick={() => dispatch(connectYouTube())}
              >
                <i className="bi bi-youtube me-1"></i>Connect YouTube to publish
              </button>
            )}
          </div>
        </div>
      )}

    </div>
  )
}
