import { createSlice } from '@reduxjs/toolkit'

const uiSlice = createSlice({
  name: 'ui',
  initialState: {
    activeTool: 'dashboard', // 'dashboard' | 'sync'
    // { platform, action: 'new'|'updated', name } — set after OAuth redirect
    notification: null,
  },
  reducers: {
    setActiveTool: (state, action) => {
      state.activeTool = action.payload
    },
    setNotification: (state, action) => {
      state.notification = action.payload
    },
    clearNotification: (state) => {
      state.notification = null
    },
  },
})

export const { setActiveTool, setNotification, clearNotification } = uiSlice.actions
export default uiSlice.reducer
