import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import api from '../api/client'

// ── Thunks ────────────────────────────────────────────────────────────────────

export const fetchLibrary = createAsyncThunk(
  'library/fetch',
  async ({ page = 1, filters = {} } = {}, { rejectWithValue }) => {
    try {
      const params = { page, ...filters }
      // Remove empty filter values
      Object.keys(params).forEach(k => {
        if (params[k] === '' || params[k] === null || params[k] === undefined) {
          delete params[k]
        }
      })
      const res = await api.get('/library/', { params })
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Failed to load library')
    }
  },
)

export const fetchLibrarySettings = createAsyncThunk(
  'library/fetchSettings',
  async (_, { rejectWithValue }) => {
    try {
      const res = await api.get('/library/settings/')
      return res.data.playlists
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Failed to load settings')
    }
  },
)

export const addLibraryPlaylist = createAsyncThunk(
  'library/addPlaylist',
  async ({ sourceId, playlistId, playlistName }, { rejectWithValue }) => {
    try {
      const res = await api.post('/library/settings/', {
        source_id: sourceId,
        playlist_id: playlistId,
        playlist_name: playlistName,
      })
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Failed to add playlist')
    }
  },
)

export const removeLibraryPlaylist = createAsyncThunk(
  'library/removePlaylist',
  async (id, { rejectWithValue }) => {
    try {
      await api.delete(`/library/settings/${id}/`)
      return id
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Failed to remove playlist')
    }
  },
)

export const syncLibraryPlaylist = createAsyncThunk(
  'library/syncPlaylist',
  async (id, { rejectWithValue }) => {
    try {
      const res = await api.post(`/library/settings/${id}/sync/`)
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Failed to sync playlist')
    }
  },
)

export const stopLibrarySync = createAsyncThunk(
  'library/stopSync',
  async (id, { rejectWithValue }) => {
    try {
      const res = await api.post(`/library/settings/${id}/stop/`)
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Failed to stop sync')
    }
  },
)

export const analyzeAllTracks = createAsyncThunk(
  'library/analyzeAll',
  async (_, { rejectWithValue }) => {
    try {
      const res = await api.post('/library/analyze-all/')
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Failed to start analysis')
    }
  },
)

export const fingerprintTrack = createAsyncThunk(
  'library/fingerprintTrack',
  async (tsId, { rejectWithValue }) => {
    try {
      const res = await api.post(`/library/tracks/${tsId}/fingerprint/`)
      return { tsId, ...res.data }
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Failed to start fingerprinting')
    }
  },
)

// ── Slice ─────────────────────────────────────────────────────────────────────

const initialState = {
  tracks: [],
  total: 0,
  page: 1,
  pages: 1,
  loading: false,
  filters: {
    q: '',
    platform: '',
    playlist_id: '',
    bpm_min: '',
    bpm_max: '',
    key: '',
    mode: '',
    sort: 'title',
  },
  trackedPlaylists: [],
  settingsLoading: false,
  error: null,
}

const librarySlice = createSlice({
  name: 'library',
  initialState,
  reducers: {
    setLibraryFilters(state, action) {
      state.filters = { ...state.filters, ...action.payload }
      state.page = 1
    },
    setLibraryPage(state, action) {
      state.page = action.payload
    },
    clearLibraryError(state) {
      state.error = null
    },
    updateTrackedPlaylist(state, action) {
      const idx = state.trackedPlaylists.findIndex(p => p.id === action.payload.id)
      if (idx !== -1) {
        state.trackedPlaylists[idx] = action.payload
      }
    },
  },
  extraReducers: builder => {
    // fetchLibrary
    builder
      .addCase(fetchLibrary.pending, state => {
        state.loading = true
        state.error = null
      })
      .addCase(fetchLibrary.fulfilled, (state, action) => {
        state.loading = false
        state.tracks = action.payload.results
        state.total = action.payload.total
        state.page = action.payload.page
        state.pages = action.payload.pages
      })
      .addCase(fetchLibrary.rejected, (state, action) => {
        state.loading = false
        state.error = action.payload
      })

    // fetchLibrarySettings
    builder
      .addCase(fetchLibrarySettings.pending, state => {
        state.settingsLoading = true
      })
      .addCase(fetchLibrarySettings.fulfilled, (state, action) => {
        state.settingsLoading = false
        state.trackedPlaylists = action.payload
      })
      .addCase(fetchLibrarySettings.rejected, (state, action) => {
        state.settingsLoading = false
        state.error = action.payload
      })

    // addLibraryPlaylist
    builder
      .addCase(addLibraryPlaylist.fulfilled, (state, action) => {
        const existing = state.trackedPlaylists.findIndex(p => p.id === action.payload.id)
        if (existing === -1) {
          state.trackedPlaylists.push(action.payload)
        } else {
          state.trackedPlaylists[existing] = action.payload
        }
      })
      .addCase(addLibraryPlaylist.rejected, (state, action) => {
        state.error = action.payload
      })

    // removeLibraryPlaylist
    builder
      .addCase(removeLibraryPlaylist.fulfilled, (state, action) => {
        state.trackedPlaylists = state.trackedPlaylists.filter(p => p.id !== action.payload)
      })
      .addCase(removeLibraryPlaylist.rejected, (state, action) => {
        state.error = action.payload
      })

    // syncLibraryPlaylist
    builder
      .addCase(syncLibraryPlaylist.fulfilled, (state, action) => {
        const idx = state.trackedPlaylists.findIndex(p => p.id === action.payload.id)
        if (idx !== -1) {
          state.trackedPlaylists[idx] = action.payload
        }
      })
      .addCase(syncLibraryPlaylist.rejected, (state, action) => {
        state.error = action.payload
      })

    // stopLibrarySync
    builder
      .addCase(stopLibrarySync.fulfilled, (state, action) => {
        const idx = state.trackedPlaylists.findIndex(p => p.id === action.payload.id)
        if (idx !== -1) {
          state.trackedPlaylists[idx] = action.payload
        }
      })
  },
})

export const {
  setLibraryFilters,
  setLibraryPage,
  clearLibraryError,
  updateTrackedPlaylist,
} = librarySlice.actions

export default librarySlice.reducer
