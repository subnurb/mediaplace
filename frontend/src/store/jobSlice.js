import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import api from '../api/client'
import { fetchMe, loginUser, registerUser } from './authSlice'

export const uploadFiles = createAsyncThunk(
  'job/uploadFiles',
  async (formData, { rejectWithValue }) => {
    try {
      const res = await api.post('/jobs/file/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Upload failed')
    }
  },
)

export const uploadFromUrl = createAsyncThunk(
  'job/uploadFromUrl',
  async (payload, { rejectWithValue }) => {
    try {
      const res = await api.post('/jobs/url/', payload)
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Download failed')
    }
  },
)

export const publishVideo = createAsyncThunk(
  'job/publish',
  async (_, { rejectWithValue }) => {
    try {
      const res = await api.post('/jobs/publish/')
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Publish failed')
    }
  },
)

const jobSlice = createSlice({
  name: 'job',
  initialState: {
    pendingJob: null,
    loading: false,
    error: null,
    videoReady: false,
    success: false,
    videoId: null,
    youtubeSignupRequired: false,
    activeTab: 'file',
  },
  reducers: {
    setActiveTab: (state, action) => { state.activeTab = action.payload },
    clearJobState: (state) => {
      state.pendingJob = null
      state.videoReady = false
      state.success = false
      state.videoId = null
      state.youtubeSignupRequired = false
      state.error = null
    },
    clearError: (state) => { state.error = null },
  },
  extraReducers: (builder) => {
    const pending = (state) => { state.loading = true; state.error = null }
    const rejected = (state, action) => { state.loading = false; state.error = action.payload }

    builder
      // Restore pending job from server on session load / login
      .addCase(fetchMe.fulfilled, (state, action) => {
        if (action.payload.pending_job) {
          state.pendingJob = action.payload.pending_job
          state.videoReady = true
        }
      })
      .addCase(loginUser.fulfilled, (state, action) => {
        if (action.payload.pending_job) {
          state.pendingJob = action.payload.pending_job
          state.videoReady = true
        }
      })
      .addCase(registerUser.fulfilled, (state) => {
        // New user has no pending job
        state.pendingJob = null
        state.videoReady = false
      })

      .addCase(uploadFiles.pending, pending)
      .addCase(uploadFiles.fulfilled, (state, action) => {
        state.loading = false
        state.videoReady = true
        state.pendingJob = action.payload.job
      })
      .addCase(uploadFiles.rejected, rejected)

      .addCase(uploadFromUrl.pending, pending)
      .addCase(uploadFromUrl.fulfilled, (state, action) => {
        state.loading = false
        state.videoReady = true
        state.pendingJob = action.payload.job
      })
      .addCase(uploadFromUrl.rejected, rejected)

      .addCase(publishVideo.pending, pending)
      .addCase(publishVideo.fulfilled, (state, action) => {
        state.loading = false
        if (action.payload.youtube_signup_required) {
          state.youtubeSignupRequired = true
        } else {
          state.success = true
          state.videoId = action.payload.video_id
          state.videoReady = false
          state.pendingJob = null
        }
      })
      .addCase(publishVideo.rejected, rejected)
  },
})

export const { setActiveTab, clearJobState, clearError } = jobSlice.actions
export default jobSlice.reducer
