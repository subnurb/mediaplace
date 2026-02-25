import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import api from '../api/client'

export const fetchMe = createAsyncThunk('auth/fetchMe', async (_, { rejectWithValue }) => {
  try {
    const res = await api.get('/auth/me/')
    return res.data
  } catch {
    return rejectWithValue(null) // 401 means not logged in
  }
})

export const registerUser = createAsyncThunk(
  'auth/register',
  async (data, { rejectWithValue }) => {
    try {
      const res = await api.post('/auth/register/', data)
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Registration failed')
    }
  },
)

export const loginUser = createAsyncThunk(
  'auth/login',
  async (data, { rejectWithValue }) => {
    try {
      const res = await api.post('/auth/login/', data)
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Login failed')
    }
  },
)

export const logoutUser = createAsyncThunk('auth/logout', async () => {
  await api.post('/auth/logout/')
})

export const updateProfile = createAsyncThunk(
  'auth/updateProfile',
  async (data, { rejectWithValue }) => {
    try {
      const res = await api.put('/auth/profile/', data)
      return res.data.user
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Failed to update profile')
    }
  },
)

export const changePassword = createAsyncThunk(
  'auth/changePassword',
  async (data, { rejectWithValue }) => {
    try {
      await api.post('/auth/change-password/', data)
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Failed to change password')
    }
  },
)

const authSlice = createSlice({
  name: 'auth',
  initialState: {
    user: null,
    loading: true, // true on startup: wait for session check before rendering
    error: null,
  },
  reducers: {
    clearError: (state) => { state.error = null },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchMe.pending, (state) => { state.loading = true })
      .addCase(fetchMe.fulfilled, (state, action) => {
        state.loading = false
        state.user = action.payload.user
      })
      .addCase(fetchMe.rejected, (state) => {
        state.loading = false
        state.user = null
      })
      .addCase(registerUser.fulfilled, (state, action) => {
        state.user = action.payload.user
        state.error = null
      })
      .addCase(registerUser.rejected, (state, action) => { state.error = action.payload })
      .addCase(loginUser.fulfilled, (state, action) => {
        state.user = action.payload.user
        state.error = null
      })
      .addCase(loginUser.rejected, (state, action) => { state.error = action.payload })
      .addCase(logoutUser.fulfilled, (state) => { state.user = null })
      .addCase(updateProfile.fulfilled, (state, action) => {
        state.user = action.payload
        state.error = null
      })
      .addCase(updateProfile.rejected, (state, action) => { state.error = action.payload })
      .addCase(changePassword.rejected, (state, action) => { state.error = action.payload })
  },
})

export const { clearError } = authSlice.actions
export default authSlice.reducer
