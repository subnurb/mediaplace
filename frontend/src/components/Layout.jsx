import React, { useState, useCallback, useEffect } from 'react'
import { useSelector, useDispatch } from 'react-redux'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { logoutUser, clearUser } from '../store/authSlice'
import api from '../api/client'
import { connectYouTube, connectSoundCloud, connectSpotify, deleteSource } from '../store/sourcesSlice'
import { clearNotification } from '../store/uiSlice'

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

const ROUTE_TITLES = [
  { path: '/',                  icon: 'bi-youtube text-danger',           label: 'MP3 to YouTube Publisher' },
  { path: '/sync',              icon: 'bi-arrow-left-right text-primary', label: 'Sync Playlists'           },
  { path: '/sync/log',          icon: 'bi-clock-history text-primary',    label: 'Sync History'             },
  { path: '/library',           icon: 'bi-music-note-list text-success',  label: 'Library'                  },
  { path: '/library/settings',  icon: 'bi-gear text-secondary',           label: 'Library Settings'         },
  { path: '/profile',           icon: 'bi-person-circle text-secondary',  label: 'My Profile'               },
]

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

function SidebarNavItem({ to, icon, label, end, onClick }) {
  return (
    <li className="nav-item">
      <NavLink
        to={to}
        end={end}
        onClick={onClick}
        className={({ isActive }) =>
          `nav-link w-100 text-start border-0 bg-transparent ${isActive ? 'active' : ''}`
        }
      >
        <i className={`nav-icon bi ${icon}`}></i>
        <p>{label}</p>
      </NavLink>
    </li>
  )
}

export default function Layout({ children }) {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const location = useLocation()
  const { user } = useSelector((s) => s.auth)
  const { items: sources, error: sourcesError } = useSelector((s) => s.sources)
  const { notification } = useSelector((s) => s.ui)

  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [showDeleteModal, setShowDeleteModal] = useState(false)

  const toggleSidebar = useCallback(() => {
    setSidebarOpen((prev) => !prev)
  }, [])

  useEffect(() => {
    setSidebarOpen(false)
  }, [location.pathname])

  useEffect(() => {
    document.body.classList.toggle('sidebar-open', sidebarOpen)
    return () => document.body.classList.remove('sidebar-open')
  }, [sidebarOpen])

  const youtubeSources = sources.filter((s) => s.source_type === 'youtube_publish')
  const soundcloudSources = sources.filter((s) => s.source_type === 'soundcloud')
  const spotifySources = sources.filter((s) => s.source_type === 'spotify')

  const currentRoute = ROUTE_TITLES.find((r) => {
    if (r.path === '/') return location.pathname === '/'
    return location.pathname.startsWith(r.path)
  }) || ROUTE_TITLES[0]

  const handleDeleteAccountConfirm = async () => {
    try {
      await api.post('/auth/delete-account/')
      setShowDeleteModal(false)
      dispatch(clearUser())
      navigate('/')
    } catch (err) {
      const msg = err.response?.data?.error || err.message || 'Account deletion failed'
      window.alert(msg)
    }
  }

  return (
    <div className="app-wrapper">

      {/* ── Top Navbar ── */}
      <nav className="app-header navbar navbar-expand bg-body">
        <div className="container-fluid">
          <button
            className="btn btn-sm btn-light border d-lg-none me-2"
            onClick={toggleSidebar}
            aria-label="Toggle sidebar"
          >
            <i className="bi bi-list fs-5"></i>
          </button>

          <NavLink className="navbar-brand" to="/">
            <i className="bi bi-play-circle-fill text-danger me-2"></i>
            <span className="fw-bold">MediaPlace</span>
          </NavLink>

          <div className="ms-auto d-flex align-items-center gap-3">
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
                    onClick={() => navigate('/profile')}
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
                <li>
                  <button
                    className="dropdown-item text-danger"
                    onClick={() => setShowDeleteModal(true)}
                  >
                    <i className="bi bi-trash me-2"></i>Delete account…
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
          <NavLink to="/" className="brand-link px-3 py-3 d-flex align-items-center gap-2">
            <i className="bi bi-music-note-beamed fs-4 text-danger"></i>
            <span className="brand-text fw-bold">MP3 → YouTube</span>
          </NavLink>
        </div>

        <div className="sidebar-wrapper">
          <nav className="mt-2">
            <ul className="nav sidebar-menu flex-column" data-lte-toggle="treeview">

              <li className="nav-header text-uppercase small px-3 pb-1">Tools</li>

              <SidebarNavItem to="/" icon="bi-youtube" label="MP3 → YouTube" end />
              <SidebarNavItem to="/sync" icon="bi-arrow-left-right" label="Sync Playlists" end />
              <SidebarNavItem to="/sync/log" icon="bi-clock-history" label="Sync History" end />
              <SidebarNavItem to="/library" icon="bi-music-note-list" label="Library" end />
              <SidebarNavItem to="/library/settings" icon="bi-gear" label="Library Settings" end />

              {/* Sources */}
              <li className="nav-header text-uppercase small px-3 pb-1 mt-2">Sources</li>

              {sourcesError && (
                <li className="px-3 py-1">
                  <span className="text-danger small">{sourcesError}</span>
                </li>
              )}

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

              <li className="nav-item px-3 py-1">
                <button
                  className="btn btn-sm btn-outline-danger w-100 d-flex align-items-center gap-2 justify-content-center"
                  onClick={() => dispatch(connectYouTube())}
                >
                  <i className="bi bi-youtube"></i>
                  {youtubeSources.length > 0 ? 'Add channel' : 'Connect YouTube'}
                </button>
              </li>

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

              <li className="nav-item px-3 py-1">
                <button
                  className="btn btn-sm btn-outline-warning w-100 d-flex align-items-center gap-2 justify-content-center"
                  onClick={() => dispatch(connectSoundCloud())}
                >
                  <i className="bi bi-soundwave"></i>
                  {soundcloudSources.length > 0 ? 'Add account' : 'Connect SoundCloud'}
                </button>
              </li>

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

              <li className="nav-item px-3 py-1">
                <button
                  className="btn btn-sm btn-outline-success w-100 d-flex align-items-center gap-2 justify-content-center"
                  onClick={() => dispatch(connectSpotify())}
                >
                  <i className="bi bi-music-note-beamed"></i>
                  {spotifySources.length > 0 ? 'Add account' : 'Connect Spotify'}
                </button>
              </li>

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

          <div className="mt-auto p-3 border-top small text-muted">
            <i className="bi bi-person-circle me-1"></i>
            <span>{user?.username}</span>
          </div>
        </div>
      </aside>

      {sidebarOpen && (
        <div
          className="d-lg-none"
          onClick={() => setSidebarOpen(false)}
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
            zIndex: 1037,
          }}
        />
      )}

      {/* Delete account confirmation modal */}
      {showDeleteModal && (
        <div
          className="modal fade show"
          style={{ display: 'block', backgroundColor: 'rgba(0,0,0,0.5)' }}
          tabIndex="-1"
          role="dialog"
          aria-modal="true"
        >
          <div className="modal-dialog modal-dialog-centered" role="document">
            <div className="modal-content">
              <div className="modal-header">
                <h5 className="modal-title text-danger">Delete account</h5>
                <button
                  type="button"
                  className="btn-close"
                  aria-label="Close"
                  onClick={() => setShowDeleteModal(false)}
                />
              </div>
              <div className="modal-body">
                <p className="mb-0">
                  This will permanently delete your MediaPlace account and all associated data.
                  This action cannot be undone.
                </p>
              </div>
              <div className="modal-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowDeleteModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={handleDeleteAccountConfirm}
                >
                  Yes, delete my account
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Main Content ── */}
      <main className="app-main">
        <div className="app-content-header py-3 px-4 border-bottom">
          <div className="container-fluid px-0">
            <h2 className="page-title h5 mb-0 fw-semibold">
              <i className={`bi ${currentRoute.icon} me-2`}></i>
              {currentRoute.label}
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
