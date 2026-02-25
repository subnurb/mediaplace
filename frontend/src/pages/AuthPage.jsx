import React, { useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { loginUser, registerUser, clearError } from '../store/authSlice'
import api from '../api/client'

export default function AuthPage() {
  const dispatch = useDispatch()
  const { error } = useSelector((s) => s.auth)

  const [tab, setTab] = useState('login')
  const [loading, setLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)
  const [form, setForm] = useState({ username: '', email: '', password: '' })

  const set = (field) => (e) => setForm((p) => ({ ...p, [field]: e.target.value }))

  const switchTab = (t) => {
    setTab(t)
    setForm({ username: '', email: '', password: '' })
    dispatch(clearError())
  }

  const handleGoogleLogin = async () => {
    setGoogleLoading(true)
    try {
      const res = await api.get('/auth/google/')
      window.location.href = res.data.auth_url
    } catch {
      setGoogleLoading(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    dispatch(clearError())
    setLoading(true)
    if (tab === 'login') {
      await dispatch(loginUser({ username: form.username, password: form.password }))
    } else {
      await dispatch(registerUser(form))
    }
    setLoading(false)
  }

  return (
    <div
      className="min-vh-100 d-flex align-items-center justify-content-center"
      style={{ background: 'var(--bs-body-bg)' }}
    >
      <div className="card shadow-lg border-0" style={{ width: '100%', maxWidth: 420 }}>

        {/* Header */}
        <div className="card-header text-center py-4 bg-danger border-0 rounded-top-3">
          <i className="bi bi-play-circle-fill text-white" style={{ fontSize: '2.5rem' }}></i>
          <h4 className="fw-bold text-white mt-2 mb-0">MediaPlace</h4>
          <p className="text-white-50 small mb-0">MP3 → YouTube Publisher</p>
        </div>

        <div className="card-body p-4">

          {/* Tab switcher */}
          <ul className="nav nav-pills nav-justified mb-4 bg-body-secondary rounded p-1">
            <li className="nav-item">
              <button
                className={`nav-link w-100 border-0 ${tab === 'login' ? 'active' : ''}`}
                onClick={() => switchTab('login')}
              >
                Sign in
              </button>
            </li>
            <li className="nav-item">
              <button
                className={`nav-link w-100 border-0 ${tab === 'register' ? 'active' : ''}`}
                onClick={() => switchTab('register')}
              >
                Create account
              </button>
            </li>
          </ul>

          {/* Error */}
          {error && (
            <div className="alert alert-danger d-flex align-items-center gap-2 py-2 small" role="alert">
              <i className="bi bi-exclamation-circle-fill flex-shrink-0"></i>
              <span>{error}</span>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} noValidate>
            <div className="mb-3">
              <label className="form-label fw-semibold small">
                {tab === 'login' ? 'Username or email' : 'Username'}
              </label>
              <div className="input-group">
                <span className="input-group-text bg-body-secondary border-end-0">
                  <i className="bi bi-person text-muted"></i>
                </span>
                <input
                  type="text"
                  className="form-control border-start-0 ps-0"
                  value={form.username}
                  onChange={set('username')}
                  placeholder={tab === 'login' ? 'username or email' : 'your_username'}
                  required
                  autoFocus
                  autoComplete="username"
                />
              </div>
            </div>

            {tab === 'register' && (
              <div className="mb-3">
                <label className="form-label fw-semibold small">
                  Email <span className="text-muted fw-normal">(optional)</span>
                </label>
                <div className="input-group">
                  <span className="input-group-text bg-body-secondary border-end-0">
                    <i className="bi bi-envelope text-muted"></i>
                  </span>
                  <input
                    type="email"
                    className="form-control border-start-0 ps-0"
                    value={form.email}
                    onChange={set('email')}
                    placeholder="you@example.com"
                    autoComplete="email"
                  />
                </div>
              </div>
            )}

            <div className="mb-4">
              <label className="form-label fw-semibold small">Password</label>
              <div className="input-group">
                <span className="input-group-text bg-body-secondary border-end-0">
                  <i className="bi bi-lock text-muted"></i>
                </span>
                <input
                  type="password"
                  className="form-control border-start-0 ps-0"
                  value={form.password}
                  onChange={set('password')}
                  placeholder="••••••••"
                  required
                  minLength={6}
                  autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
                />
              </div>
              {tab === 'register' && (
                <div className="form-text">Minimum 6 characters.</div>
              )}
            </div>

            <button type="submit" className="btn btn-danger w-100 py-2 fw-semibold" disabled={loading}>
              {loading ? (
                <>
                  <span className="spinner-border spinner-border-sm me-2" />
                  {tab === 'login' ? 'Signing in…' : 'Creating account…'}
                </>
              ) : tab === 'login' ? (
                <><i className="bi bi-box-arrow-in-right me-2"></i>Sign in</>
              ) : (
                <><i className="bi bi-person-plus me-2"></i>Create account</>
              )}
            </button>
          </form>

          {/* Google sign-in */}
          <div className="d-flex align-items-center gap-2 my-3">
            <hr className="flex-grow-1 m-0" />
            <span className="small text-muted">or</span>
            <hr className="flex-grow-1 m-0" />
          </div>
          <button
            className="btn btn-outline-secondary w-100 py-2 d-flex align-items-center justify-content-center gap-2"
            onClick={handleGoogleLogin}
            disabled={googleLoading}
            type="button"
          >
            {googleLoading ? (
              <span className="spinner-border spinner-border-sm" />
            ) : (
              <svg width="18" height="18" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
                <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
                <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
                <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
                <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
                <path fill="none" d="M0 0h48v48H0z"/>
              </svg>
            )}
            <span className="fw-semibold">Continue with Google</span>
          </button>

        </div>
      </div>
    </div>
  )
}
