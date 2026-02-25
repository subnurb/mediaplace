import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'
import api from '../api/client'

// ── Thunks ────────────────────────────────────────────────────────────────────

export const fetchPlaylists = createAsyncThunk(
  'sync/fetchPlaylists',
  async (sourceId, { rejectWithValue }) => {
    try {
      const res = await api.get(`/sources/${sourceId}/playlists/`)
      return { sourceId, playlists: res.data.playlists }
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Failed to load playlists')
    }
  },
)

export const createSyncJob = createAsyncThunk(
  'sync/createJob',
  async ({ sourceFromId, sourceToId, playlistId, playlistName }, { rejectWithValue }) => {
    try {
      const res = await api.post('/sync/', {
        source_from: sourceFromId,
        source_to: sourceToId,
        playlist_id: playlistId,
        playlist_name: playlistName,
      })
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Failed to create sync job')
    }
  },
)

export const analyzeSyncJob = createAsyncThunk(
  'sync/analyze',
  async (jobId, { rejectWithValue }) => {
    try {
      const res = await api.post(`/sync/${jobId}/analyze/`)
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Failed to start analysis')
    }
  },
)

export const pollSyncJob = createAsyncThunk(
  'sync/poll',
  async (jobId, { rejectWithValue }) => {
    try {
      const res = await api.get(`/sync/${jobId}/`)
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Failed to fetch job status')
    }
  },
)

export const uploadTrack = createAsyncThunk(
  'sync/uploadTrack',
  async ({ jobId, trackId }, { rejectWithValue }) => {
    try {
      const res = await api.post(`/sync/${jobId}/tracks/${trackId}/upload/`)
      return res.data  // returns the updated track
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Upload failed')
    }
  },
)

export const skipTrack = createAsyncThunk(
  'sync/skipTrack',
  async ({ jobId, trackId }, { rejectWithValue }) => {
    try {
      const res = await api.post(`/sync/${jobId}/tracks/${trackId}/skip/`)
      return res.data  // returns the updated track
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Skip failed')
    }
  },
)

export const confirmTrack = createAsyncThunk(
  'sync/confirmTrack',
  async ({ jobId, trackId }, { rejectWithValue }) => {
    try {
      const res = await api.post(`/sync/${jobId}/tracks/${trackId}/confirm/`)
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Confirm failed')
    }
  },
)

export const rejectTrack = createAsyncThunk(
  'sync/rejectTrack',
  async ({ jobId, trackId }, { rejectWithValue }) => {
    try {
      const res = await api.post(`/sync/${jobId}/tracks/${trackId}/reject/`)
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Reject failed')
    }
  },
)

export const pushToPlaylist = createAsyncThunk(
  'sync/push',
  async ({ jobId, targetPlaylistId, newPlaylistName }, { rejectWithValue }) => {
    try {
      const res = await api.post(`/sync/${jobId}/push/`, {
        target_playlist_id: targetPlaylistId || null,
        new_playlist_name: newPlaylistName || '',
      })
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Push failed')
    }
  },
)

export const loadJob = createAsyncThunk(
  'sync/loadJob',
  async (jobId, { rejectWithValue }) => {
    try {
      const res = await api.get(`/sync/${jobId}/`)
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Failed to load job')
    }
  },
)

export const selectMatch = createAsyncThunk(
  'sync/selectMatch',
  async ({ jobId, trackId, videoId }, { rejectWithValue }) => {
    try {
      const res = await api.post(`/sync/${jobId}/tracks/${trackId}/select/`, { video_id: videoId })
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Failed to select match')
    }
  },
)

export const unconfirmTrack = createAsyncThunk(
  'sync/unconfirmTrack',
  async ({ jobId, trackId }, { rejectWithValue }) => {
    try {
      const res = await api.post(`/sync/${jobId}/tracks/${trackId}/unconfirm/`)
      return res.data
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Unconfirm failed')
    }
  },
)

export const confirmAllTracks = createAsyncThunk(
  'sync/confirmAll',
  async (jobId, { rejectWithValue }) => {
    try {
      const res = await api.post(`/sync/${jobId}/confirm-all/`)
      return res.data  // { confirmed: N, tracks: [...] }
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Confirm all failed')
    }
  },
)

export const resolveTrackUrl = createAsyncThunk(
  'sync/resolveTrackUrl',
  async ({ jobId, trackId, url }, { rejectWithValue }) => {
    try {
      const res = await api.post(`/sync/${jobId}/tracks/${trackId}/resolve-url/`, { url })
      return res.data  // { video_id, title, artist }
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Failed to resolve URL')
    }
  },
)

export const fetchSyncLog = createAsyncThunk(
  'sync/fetchLog',
  async (_, { rejectWithValue }) => {
    try {
      const res = await api.get('/sync/log/')
      return res.data.jobs
    } catch (err) {
      return rejectWithValue(err.response?.data?.error || 'Failed to load sync log')
    }
  },
)

// ── Helpers ───────────────────────────────────────────────────────────────────

function replaceTrack(tracks, updated) {
  return tracks.map((t) => (t.id === updated.id ? updated : t))
}

// ── Slice ─────────────────────────────────────────────────────────────────────

const syncSlice = createSlice({
  name: 'sync',
  initialState: {
    // Playlists per source id: { [sourceId]: [...] }
    playlists: {},
    playlistsLoading: false,

    // Active sync job
    job: null,
    jobLoading: false,

    // Push state
    pushLoading: false,

    // Sync history log
    syncLog: [],
    syncLogLoading: false,

    error: null,
  },
  reducers: {
    clearJob: (state) => {
      state.job = null
      state.error = null
    },
    clearError: (state) => {
      state.error = null
    },
  },
  extraReducers: (builder) => {
    builder
      // fetchPlaylists
      .addCase(fetchPlaylists.pending, (state) => {
        state.playlistsLoading = true
        state.error = null
      })
      .addCase(fetchPlaylists.fulfilled, (state, action) => {
        state.playlistsLoading = false
        state.playlists[action.payload.sourceId] = action.payload.playlists
      })
      .addCase(fetchPlaylists.rejected, (state, action) => {
        state.playlistsLoading = false
        state.error = action.payload
      })

      // createSyncJob
      .addCase(createSyncJob.pending, (state) => {
        state.jobLoading = true
        state.error = null
      })
      .addCase(createSyncJob.fulfilled, (state, action) => {
        state.jobLoading = false
        state.job = action.payload
      })
      .addCase(createSyncJob.rejected, (state, action) => {
        state.jobLoading = false
        state.error = action.payload
      })

      // analyzeSyncJob — updates job status
      .addCase(analyzeSyncJob.fulfilled, (state, action) => {
        if (state.job) state.job = { ...state.job, ...action.payload }
      })
      .addCase(analyzeSyncJob.rejected, (state, action) => {
        state.error = action.payload
      })

      // pollSyncJob — replaces entire job (includes updated tracks)
      .addCase(pollSyncJob.fulfilled, (state, action) => {
        state.job = action.payload
      })

      // uploadTrack / skipTrack — update the individual track in place
      .addCase(uploadTrack.fulfilled, (state, action) => {
        if (state.job?.tracks) {
          state.job.tracks = replaceTrack(state.job.tracks, action.payload)
        }
      })
      .addCase(uploadTrack.rejected, (state, action) => {
        state.error = action.payload
      })

      .addCase(skipTrack.fulfilled, (state, action) => {
        if (state.job?.tracks) {
          state.job.tracks = replaceTrack(state.job.tracks, action.payload)
        }
      })
      .addCase(skipTrack.rejected, (state, action) => {
        state.error = action.payload
      })

      .addCase(confirmTrack.fulfilled, (state, action) => {
        if (state.job?.tracks) {
          state.job.tracks = replaceTrack(state.job.tracks, action.payload)
        }
      })
      .addCase(confirmTrack.rejected, (state, action) => {
        state.error = action.payload
      })

      .addCase(rejectTrack.fulfilled, (state, action) => {
        if (state.job?.tracks) {
          state.job.tracks = replaceTrack(state.job.tracks, action.payload)
        }
      })
      .addCase(rejectTrack.rejected, (state, action) => {
        state.error = action.payload
      })

      .addCase(selectMatch.fulfilled, (state, action) => {
        if (state.job?.tracks) {
          state.job.tracks = replaceTrack(state.job.tracks, action.payload)
        }
      })
      .addCase(selectMatch.rejected, (state, action) => {
        state.error = action.payload
      })

      .addCase(unconfirmTrack.fulfilled, (state, action) => {
        if (state.job?.tracks) {
          state.job.tracks = replaceTrack(state.job.tracks, action.payload)
        }
      })
      .addCase(unconfirmTrack.rejected, (state, action) => {
        state.error = action.payload
      })

      .addCase(confirmAllTracks.fulfilled, (state, action) => {
        if (state.job?.tracks) {
          for (const updated of action.payload.tracks) {
            state.job.tracks = replaceTrack(state.job.tracks, updated)
          }
        }
      })
      .addCase(confirmAllTracks.rejected, (state, action) => {
        state.error = action.payload
      })

      // pushToPlaylist — transitions job to SYNCING; poll updates to DONE
      .addCase(pushToPlaylist.pending, (state) => {
        state.pushLoading = true
        state.error = null
      })
      .addCase(pushToPlaylist.fulfilled, (state) => {
        state.pushLoading = false
        // Backend returns {"status":"syncing"} — not a full job object.
        // Just flip the status so polling kicks in; the poll response will
        // deliver the complete updated job (including id, tracks, etc.).
        if (state.job) state.job = { ...state.job, status: 'syncing' }
      })
      .addCase(pushToPlaylist.rejected, (state, action) => {
        state.pushLoading = false
        state.error = action.payload
      })

      // loadJob — reload full job (used by SyncLogPage Resume)
      .addCase(loadJob.pending, (state) => {
        state.jobLoading = true
        state.error = null
      })
      .addCase(loadJob.fulfilled, (state, action) => {
        state.jobLoading = false
        state.job = action.payload
      })
      .addCase(loadJob.rejected, (state, action) => {
        state.jobLoading = false
        state.error = action.payload
      })

      // fetchSyncLog
      .addCase(fetchSyncLog.pending, (state) => {
        state.syncLogLoading = true
        state.error = null
      })
      .addCase(fetchSyncLog.fulfilled, (state, action) => {
        state.syncLogLoading = false
        state.syncLog = action.payload
      })
      .addCase(fetchSyncLog.rejected, (state, action) => {
        state.syncLogLoading = false
        state.error = action.payload
      })
  },
})

export const { clearJob, clearError } = syncSlice.actions
export default syncSlice.reducer
