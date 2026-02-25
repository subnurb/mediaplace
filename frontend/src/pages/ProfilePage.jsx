import React, { useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { updateProfile, changePassword, clearError } from '../store/authSlice'

export default function ProfilePage() {
  const dispatch = useDispatch()
  const { user, error } = useSelector((s) => s.auth)

  // Profile form state
  const [username, setUsername] = useState(user?.username || '')
  const [email, setEmail] = useState(user?.email || '')
  const [profileSaving, setProfileSaving] = useState(false)
  const [profileSuccess, setProfileSuccess] = useState(false)

  // Password form state
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordSaving, setPasswordSaving] = useState(false)
  const [passwordSuccess, setPasswordSuccess] = useState(false)
  const [passwordError, setPasswordError] = useState('')

  async function handleProfileSave(e) {
    e.preventDefault()
    dispatch(clearError())
    setProfileSuccess(false)
    setProfileSaving(true)
    const result = await dispatch(updateProfile({ username, email }))
    setProfileSaving(false)
    if (!result.error) {
      setProfileSuccess(true)
      setTimeout(() => setProfileSuccess(false), 3000)
    }
  }

  async function handlePasswordChange(e) {
    e.preventDefault()
    setPasswordError('')
    setPasswordSuccess(false)

    if (newPassword !== confirmPassword) {
      setPasswordError('New passwords do not match.')
      return
    }
    if (newPassword.length < 6) {
      setPasswordError('Password must be at least 6 characters.')
      return
    }

    setPasswordSaving(true)
    const result = await dispatch(changePassword({ current_password: currentPassword, new_password: newPassword }))
    setPasswordSaving(false)

    if (result.error) {
      setPasswordError(result.payload || 'Failed to change password.')
    } else {
      setPasswordSuccess(true)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setTimeout(() => setPasswordSuccess(false), 3000)
    }
  }

  return (
    <div className="row g-4 mt-1" style={{ maxWidth: 640 }}>

      {/* ── Profile info ── */}
      <div className="col-12">
        <div className="card shadow-sm">
          <div className="card-header">
            <i className="bi bi-person-circle me-2"></i>Profile Information
          </div>
          <div className="card-body">
            {error && (
              <div className="alert alert-danger py-2 small">
                <i className="bi bi-exclamation-circle me-1"></i>{error}
              </div>
            )}
            {profileSuccess && (
              <div className="alert alert-success py-2 small">
                <i className="bi bi-check-circle me-1"></i>Profile updated successfully.
              </div>
            )}
            <form onSubmit={handleProfileSave}>
              <div className="mb-3">
                <label className="form-label fw-semibold">Username</label>
                <input
                  type="text"
                  className="form-control"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  autoComplete="username"
                />
              </div>
              <div className="mb-3">
                <label className="form-label fw-semibold">Email address</label>
                <input
                  type="email"
                  className="form-control"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="No email set"
                  autoComplete="email"
                />
                <div className="form-text">Used for account recovery. Not shared publicly.</div>
              </div>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={profileSaving}
              >
                {profileSaving
                  ? <><span className="spinner-border spinner-border-sm me-2"></span>Saving…</>
                  : <><i className="bi bi-check-lg me-1"></i>Save changes</>
                }
              </button>
            </form>
          </div>
        </div>
      </div>

      {/* ── Change password ── */}
      <div className="col-12">
        <div className="card shadow-sm">
          <div className="card-header">
            <i className="bi bi-shield-lock me-2"></i>Change Password
          </div>
          <div className="card-body">
            {passwordError && (
              <div className="alert alert-danger py-2 small">
                <i className="bi bi-exclamation-circle me-1"></i>{passwordError}
              </div>
            )}
            {passwordSuccess && (
              <div className="alert alert-success py-2 small">
                <i className="bi bi-check-circle me-1"></i>Password changed successfully.
              </div>
            )}
            <form onSubmit={handlePasswordChange}>
              <div className="mb-3">
                <label className="form-label fw-semibold">Current password</label>
                <input
                  type="password"
                  className="form-control"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                />
              </div>
              <div className="mb-3">
                <label className="form-label fw-semibold">New password</label>
                <input
                  type="password"
                  className="form-control"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  autoComplete="new-password"
                  minLength={6}
                />
                <div className="form-text">Minimum 6 characters.</div>
              </div>
              <div className="mb-3">
                <label className="form-label fw-semibold">Confirm new password</label>
                <input
                  type="password"
                  className="form-control"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  autoComplete="new-password"
                />
              </div>
              <button
                type="submit"
                className="btn btn-warning"
                disabled={passwordSaving}
              >
                {passwordSaving
                  ? <><span className="spinner-border spinner-border-sm me-2"></span>Changing…</>
                  : <><i className="bi bi-key me-1"></i>Change password</>
                }
              </button>
            </form>
          </div>
        </div>
      </div>

    </div>
  )
}
