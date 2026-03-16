import { createSlice } from '@reduxjs/toolkit'

const uiSlice = createSlice({
  name: 'ui',
  initialState: {
    // { platform, action: 'new'|'updated'|'error', name } — set after OAuth redirect
    notification: null,
  },
  reducers: {
    setNotification: (state, action) => {
      state.notification = action.payload
    },
    clearNotification: (state) => {
      state.notification = null
    },
  },
})

export const { setNotification, clearNotification } = uiSlice.actions
export default uiSlice.reducer
