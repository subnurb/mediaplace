import React, { useEffect } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { Routes, Route, Navigate, useSearchParams, useNavigate } from 'react-router-dom'
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

function OAuthRedirectHandler() {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  useEffect(() => {
    if (searchParams.has('youtube')) {
      dispatch(setNotification({ platform: 'youtube', action: searchParams.get('youtube'), name: searchParams.get('name') }))
      navigate('/', { replace: true })
    } else if (searchParams.has('soundcloud')) {
      dispatch(setNotification({ platform: 'soundcloud', action: searchParams.get('soundcloud'), name: searchParams.get('name') }))
      navigate('/', { replace: true })
    } else if (searchParams.has('spotify')) {
      dispatch(setNotification({ platform: 'spotify', action: searchParams.get('spotify'), name: searchParams.get('name') }))
      navigate('/', { replace: true })
    } else if (searchParams.has('google')) {
      navigate('/', { replace: true })
    } else if (searchParams.has('auth_error')) {
      dispatch(setNotification({ platform: null, action: 'error', name: searchParams.get('auth_error') }))
      navigate('/', { replace: true })
    }
  }, [dispatch, navigate, searchParams])

  return null
}

export default function App() {
  const dispatch = useDispatch()
  const { user, loading } = useSelector((s) => s.auth)

  useEffect(() => {
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
    return (
      <>
        <OAuthRedirectHandler />
        <AuthPage />
      </>
    )
  }

  return (
    <>
      <OAuthRedirectHandler />
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/sync" element={<SyncPage />} />
          <Route path="/sync/log" element={<SyncLogPage />} />
          <Route path="/library" element={<LibraryPage />} />
          <Route path="/library/settings" element={<LibrarySettingsPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </>
  )
}
