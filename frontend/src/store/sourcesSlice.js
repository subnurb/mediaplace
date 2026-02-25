import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import api from '../api/client'
import { fetchMe, loginUser, logoutUser } from './authSlice'

export const connectYouTube = createAsyncThunk(
  'sources/connectYouTube',
  async (_, { rejectWithValue }) => {
    try {
      const res = await api.get('/auth/youtube-connect/')
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Could not start YouTube connection')
    }
  },
)

export const connectSoundCloud = createAsyncThunk(
  'sources/connectSoundCloud',
  async (_, { rejectWithValue }) => {
    try {
      const res = await api.get('/auth/soundcloud-connect/')
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Could not start SoundCloud connection')
    }
  },
)

export const deleteSource = createAsyncThunk(
  'sources/delete',
  async (sourceId, { rejectWithValue }) => {
    try {
      await api.delete(`/sources/${sourceId}/`)
      return sourceId
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Failed to disconnect source')
    }
  },
)

const sourcesSlice = createSlice({
  name: 'sources',
  initialState: {
    items: [],
    loading: false,
    error: null,
  },
  reducers: {
    clearError: (state) => { state.error = null },
  },
  extraReducers: (builder) => {
    builder
      // Populate sources from session check and login
      .addCase(fetchMe.fulfilled, (state, action) => {
        state.items = action.payload.sources || []
      })
      .addCase(loginUser.fulfilled, (state, action) => {
        state.items = action.payload.sources || []
      })
      .addCase(logoutUser.fulfilled, (state) => {
        state.items = []
      })

      // YouTube OAuth: redirect browser to Google
      .addCase(connectYouTube.pending, (state) => { state.loading = true; state.error = null })
      .addCase(connectYouTube.fulfilled, (_state, action) => {
        if (action.payload.auth_url) window.location.href = action.payload.auth_url
      })
      .addCase(connectYouTube.rejected, (state, action) => {
        state.loading = false
        state.error = action.payload
      })

      // SoundCloud OAuth: redirect browser to SoundCloud
      .addCase(connectSoundCloud.pending, (state) => { state.loading = true; state.error = null })
      .addCase(connectSoundCloud.fulfilled, (_state, action) => {
        if (action.payload.auth_url) window.location.href = action.payload.auth_url
      })
      .addCase(connectSoundCloud.rejected, (state, action) => {
        state.loading = false
        state.error = action.payload
      })

      // Delete source
      .addCase(deleteSource.fulfilled, (state, action) => {
        state.items = state.items.filter((s) => s.id !== action.payload)
      })
      .addCase(deleteSource.rejected, (state, action) => { state.error = action.payload })
  },
})

export const { clearError } = sourcesSlice.actions
export default sourcesSlice.reducer
