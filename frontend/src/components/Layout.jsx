import React from 'react'
import { useSelector, useDispatch } from 'react-redux'
import { logoutUser } from '../store/authSlice'
import { connectYouTube, connectSoundCloud, connectSpotify, deleteSource } from '../store/sourcesSlice'
import { setActiveTool, clearNotification } from '../store/uiSlice'

const SOURCE_LABELS = {
  youtube_publish: 'YouTube',
  soundcloud: 'SoundCloud',
  spotify: 'Spotify',
  deezer: 'Deezer',
  local: 'Local Disk',
  ftp: 'FTP',
}

const SOURCE_ICONS = {
  youtube_publish: 'bi-youtube text-danger',
  soundcloud: 'bi-soundwave text-warning',
  spotify: 'bi-music-note-beamed text-success',
  deezer: 'bi-music-player text-primary',
  local: 'bi-folder text-secondary',
  ftp: 'bi-server text-secondary',
}

const PAGE_TITLES = {
  dashboard:           { icon: 'bi-youtube text-danger',           label: 'MP3 to YouTube Publisher' },
  sync:                { icon: 'bi-arrow-left-right text-primary', label: 'Sync Playlists'           },
  'sync-log':          { icon: 'bi-clock-history text-primary',    label: 'Sync History'             },
  library:             { icon: 'bi-music-note-list text-success',  label: 'Library'                  },
  'library-settings':  { icon: 'bi-gear text-secondary',           label: 'Library Settings'         },
  profile:             { icon: 'bi-person-circle text-secondary',  label: 'My Profile'               },
}

const PLATFORM_META = {
  youtube:    { label: 'YouTube',    icon: 'bi-youtube',             alertClass: 'alert-danger'  },
  soundcloud: { label: 'SoundCloud', icon: 'bi-soundwave',           alertClass: 'alert-warning' },
  spotify:    { label: 'Spotify',    icon: 'bi-music-note-beamed',   alertClass: 'alert-success' },
}

function OAuthNotification({ notification, onDismiss }) {
  if (!notification) return null

  if (notification.action === 'error') {
    return (
      <div className="alert alert-danger alert-dismissible d-flex align-items-center gap-2 mt-3" role="alert">
        <i className="bi bi-exclamation-circle-fill flex-shrink-0"></i>
        <span>Connection failed: {notification.name || 'unknown error'}</span>
        <button type="button" className="btn-close ms-auto" onClick={onDismiss} />
      </div>
    )
  }

  const meta = PLATFORM_META[notification.platform] || { label: notification.platform, icon: 'bi-plug', alertClass: 'alert-info' }
  const isNew = notification.action === 'new'

  return (
    <div className={`alert ${meta.alertClass} alert-dismissible d-flex align-items-center gap-2 mt-3`} role="alert">
      <i className={`bi ${meta.icon} flex-shrink-0`}></i>
      <span>
        {isNew
          ? <><strong>{notification.name}</strong> connected to {meta.label}.</>
          : <><strong>{notification.name}</strong> is already connected — credentials refreshed. To add a <em>different</em> {meta.label} account, sign in with another account.</>
        }
      </span>
      <button type="button" className="btn-close ms-auto" onClick={onDismiss} />
    </div>
  )
}

export default function Layout({ children }) {
  const dispatch = useDispatch()
  const { user } = useSelector((s) => s.auth)
  const { items: sources, error: sourcesError } = useSelector((s) => s.sources)
  const { activeTool, notification } = useSelector((s) => s.ui)

  const youtubeSources = sources.filter((s) => s.source_type === 'youtube_publish')
  const soundcloudSources = sources.filter((s) => s.source_type === 'soundcloud')
  const spotifySources = sources.filter((s) => s.source_type === 'spotify')

  const pageTitle = PAGE_TITLES[activeTool] || PAGE_TITLES.dashboard

  return (
    <div className="app-wrapper">

      {/* ── Top Navbar ── */}
      <nav className="app-header navbar navbar-expand bg-body">
        <div className="container-fluid">
          <a className="navbar-brand" href="/">
            <i className="bi bi-play-circle-fill text-danger me-2"></i>
            <span className="fw-bold">MediaPlace</span>
          </a>

          <div className="ms-auto d-flex align-items-center gap-3">
            {/* User menu */}
            <div className="dropdown">
              <button
                className="btn btn-sm btn-light d-flex align-items-center gap-2 border"
                data-bs-toggle="dropdown"
              >
                <i className="bi bi-person-circle"></i>
                <span className="d-none d-sm-inline fw-semibold">{user?.username}</span>
                <i className="bi bi-chevron-down small"></i>
              </button>
              <ul className="dropdown-menu dropdown-menu-end shadow-sm">
                <li>
                  <span className="dropdown-item-text small text-muted">
                    {user?.email || 'No email set'}
                  </span>
                </li>
                <li><hr className="dropdown-divider" /></li>
                <li>
                  <button
                    className="dropdown-item"
                    onClick={() => dispatch(setActiveTool('profile'))}
                  >
                    <i className="bi bi-person-circle me-2"></i>My Profile
                  </button>
                </li>
                <li><hr className="dropdown-divider" /></li>
                <li>
                  <button
                    className="dropdown-item text-danger"
                    onClick={() => dispatch(logoutUser())}
                  >
                    <i className="bi bi-box-arrow-right me-2"></i>Sign out
                  </button>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </nav>

      {/* ── Sidebar ── */}
      <aside className="app-sidebar bg-body-secondary shadow">
        <div className="sidebar-brand">
          <a href="/" className="brand-link px-3 py-3 d-flex align-items-center gap-2">
            <i className="bi bi-music-note-beamed fs-4 text-danger"></i>
            <span className="brand-text fw-bold">MP3 → YouTube</span>
          </a>
        </div>

        <div className="sidebar-wrapper">
          <nav className="mt-2">
            <ul className="nav sidebar-menu flex-column" data-lte-toggle="treeview">

              {/* Main */}
              <li className="nav-header text-uppercase small px-3 pb-1">Tools</li>
              <li className="nav-item">
                <button
                  className={`nav-link w-100 text-start border-0 bg-transparent ${activeTool === 'dashboard' ? 'active' : ''}`}
                  onClick={() => dispatch(setActiveTool('dashboard'))}
                >
                  <i className="nav-icon bi bi-youtube"></i>
                  <p>MP3 → YouTube</p>
                </button>
              </li>
              <li className="nav-item">
                <button
                  className={`nav-link w-100 text-start border-0 bg-transparent ${activeTool === 'sync' ? 'active' : ''}`}
                  onClick={() => dispatch(setActiveTool('sync'))}
                >
                  <i className="nav-icon bi bi-arrow-left-right"></i>
                  <p>Sync Playlists</p>
                </button>
              </li>
              <li className="nav-item">
                <button
                  className={`nav-link w-100 text-start border-0 bg-transparent ${activeTool === 'sync-log' ? 'active' : ''}`}
                  onClick={() => dispatch(setActiveTool('sync-log'))}
                >
                  <i className="nav-icon bi bi-clock-history"></i>
                  <p>Sync History</p>
                </button>
              </li>
              <li className="nav-item">
                <button
                  className={`nav-link w-100 text-start border-0 bg-transparent ${activeTool === 'library' ? 'active' : ''}`}
                  onClick={() => dispatch(setActiveTool('library'))}
                >
                  <i className="nav-icon bi bi-music-note-list"></i>
                  <p>Library</p>
                </button>
              </li>
              <li className="nav-item">
                <button
                  className={`nav-link w-100 text-start border-0 bg-transparent ${activeTool === 'library-settings' ? 'active' : ''}`}
                  onClick={() => dispatch(setActiveTool('library-settings'))}
                >
                  <i className="nav-icon bi bi-gear"></i>
                  <p>Library Settings</p>
                </button>
              </li>

              {/* Sources */}
              <li className="nav-header text-uppercase small px-3 pb-1 mt-2">Sources</li>

              {sourcesError && (
                <li className="px-3 py-1">
                  <span className="text-danger small">{sourcesError}</span>
                </li>
              )}

              {/* Connected YouTube channels */}
              {youtubeSources.map((source) => (
                <li key={source.id} className="nav-item">
                  <div className="nav-link d-flex align-items-center justify-content-between py-1">
                    <span className="d-flex align-items-center gap-2 text-truncate">
                      <i className={`bi ${SOURCE_ICONS.youtube_publish}`}></i>
                      <span className="small text-truncate">{source.name}</span>
                    </span>
                    <button
                      className="btn btn-link btn-sm p-0 text-muted ms-1 flex-shrink-0"
                      title="Disconnect"
                      onClick={() => dispatch(deleteSource(source.id))}
                    >
                      <i className="bi bi-x-circle"></i>
                    </button>
                  </div>
                </li>
              ))}

              {/* Connect YouTube button */}
              <li className="nav-item px-3 py-1">
                <button
                  className="btn btn-sm btn-outline-danger w-100 d-flex align-items-center gap-2 justify-content-center"
                  onClick={() => dispatch(connectYouTube())}
                >
                  <i className="bi bi-youtube"></i>
                  {youtubeSources.length > 0 ? 'Add channel' : 'Connect YouTube'}
                </button>
              </li>

              {/* Connected SoundCloud accounts */}
              {soundcloudSources.map((source) => (
                <li key={source.id} className="nav-item">
                  <div className="nav-link d-flex align-items-center justify-content-between py-1">
                    <span className="d-flex align-items-center gap-2 text-truncate">
                      <i className={`bi ${SOURCE_ICONS.soundcloud}`}></i>
                      <span className="small text-truncate">{source.name}</span>
                    </span>
                    <button
                      className="btn btn-link btn-sm p-0 text-muted ms-1 flex-shrink-0"
                      title="Disconnect"
                      onClick={() => dispatch(deleteSource(source.id))}
                    >
                      <i className="bi bi-x-circle"></i>
                    </button>
                  </div>
                </li>
              ))}

              {/* Connect SoundCloud button */}
              <li className="nav-item px-3 py-1">
                <button
                  className="btn btn-sm btn-outline-warning w-100 d-flex align-items-center gap-2 justify-content-center"
                  onClick={() => dispatch(connectSoundCloud())}
                >
                  <i className="bi bi-soundwave"></i>
                  {soundcloudSources.length > 0 ? 'Add account' : 'Connect SoundCloud'}
                </button>
              </li>

              {/* Connected Spotify accounts */}
              {spotifySources.map((source) => (
                <li key={source.id} className="nav-item">
                  <div className="nav-link d-flex align-items-center justify-content-between py-1">
                    <span className="d-flex align-items-center gap-2 text-truncate">
                      <i className={`bi ${SOURCE_ICONS.spotify}`}></i>
                      <span className="small text-truncate">{source.name}</span>
                    </span>
                    <button
                      className="btn btn-link btn-sm p-0 text-muted ms-1 flex-shrink-0"
                      title="Disconnect"
                      onClick={() => dispatch(deleteSource(source.id))}
                    >
                      <i className="bi bi-x-circle"></i>
                    </button>
                  </div>
                </li>
              ))}

              {/* Connect Spotify button */}
              <li className="nav-item px-3 py-1">
                <button
                  className="btn btn-sm btn-outline-success w-100 d-flex align-items-center gap-2 justify-content-center"
                  onClick={() => dispatch(connectSpotify())}
                >
                  <i className="bi bi-music-note-beamed"></i>
                  {spotifySources.length > 0 ? 'Add account' : 'Connect Spotify'}
                </button>
              </li>

              {/* Placeholder rows for future source types */}
              {[
                { type: 'deezer', label: 'Deezer' },
              ].map(({ type, label }) => (
                <li key={type} className="nav-item">
                  <div className="nav-link d-flex align-items-center gap-2 py-1 text-muted opacity-50" style={{ cursor: 'default' }}>
                    <i className={`bi ${SOURCE_ICONS[type]}`}></i>
                    <span className="small">{label}</span>
                    <span className="badge bg-secondary-subtle text-secondary border border-secondary-subtle ms-auto" style={{ fontSize: '0.65rem' }}>soon</span>
                  </div>
                </li>
              ))}

            </ul>
          </nav>

          {/* Sidebar footer */}
          <div className="mt-auto p-3 border-top small text-muted">
            <i className="bi bi-person-circle me-1"></i>
            <span>{user?.username}</span>
          </div>
        </div>
      </aside>

      {/* ── Main Content ── */}
      <main className="app-main">
        <div className="app-content-header py-3 px-4 border-bottom">
          <div className="container-fluid px-0">
            <h2 className="page-title h5 mb-0 fw-semibold">
              <i className={`bi ${pageTitle.icon} me-2`}></i>
              {pageTitle.label}
            </h2>
          </div>
        </div>
        <div className="app-content">
          <div className="container-fluid">
            {notification && <OAuthNotification notification={notification} onDismiss={() => dispatch(clearNotification())} />}
            {children}
          </div>
        </div>
      </main>

    </div>
  )
}
