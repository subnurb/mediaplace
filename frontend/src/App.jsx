import React, { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { fetchMe } from './store/authSlice'
import { setNotification } from './store/uiSlice'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import SyncPage from './pages/SyncPage'
import SyncLogPage from './pages/SyncLogPage'
import LibraryPage from './pages/LibraryPage'
import LibrarySettingsPage from './pages/LibrarySettingsPage'
import ProfilePage from './pages/ProfilePage'
import AuthPage from './pages/AuthPage'

export default function App() {
  const dispatch = useDispatch()
  const { user, loading } = useSelector((s) => s.auth)
  const { activeTool } = useSelector((s) => s.ui)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)

    // After an OAuth redirect, parse result params, clean URL, and set a notification
    if (params.has('youtube')) {
      dispatch(setNotification({ platform: 'youtube', action: params.get('youtube'), name: params.get('name') }))
      window.history.replaceState({}, '', '/')
    } else if (params.has('soundcloud')) {
      dispatch(setNotification({ platform: 'soundcloud', action: params.get('soundcloud'), name: params.get('name') }))
      window.history.replaceState({}, '', '/')
    } else if (params.has('google')) {
      // Google sign-in redirected back — session is already set, just clean the URL
      window.history.replaceState({}, '', '/')
    } else if (params.has('auth_error')) {
      dispatch(setNotification({ platform: null, action: 'error', name: params.get('auth_error') }))
      window.history.replaceState({}, '', '/')
    }

    dispatch(fetchMe())
  }, [dispatch])

  if (loading) {
    return (
      <div className="d-flex justify-content-center align-items-center vh-100 bg-body-tertiary">
        <div className="spinner-border text-danger" role="status">
          <span className="visually-hidden">Loading…</span>
        </div>
      </div>
    )
  }

  if (!user) {
    return <AuthPage />
  }

  return (
    <Layout>
      {activeTool === 'sync' ? <SyncPage />
        : activeTool === 'sync-log' ? <SyncLogPage />
        : activeTool === 'library' ? <LibraryPage />
        : activeTool === 'library-settings' ? <LibrarySettingsPage />
        : activeTool === 'profile' ? <ProfilePage />
        : <Dashboard />}
    </Layout>
  )
}
