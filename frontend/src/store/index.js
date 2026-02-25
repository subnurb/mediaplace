import { configureStore } from '@reduxjs/toolkit'
import authReducer from './authSlice'
import jobReducer from './jobSlice'
import sourcesReducer from './sourcesSlice'
import uiReducer from './uiSlice'
import syncReducer from './syncSlice'
import libraryReducer from './librarySlice'

export default configureStore({
  reducer: {
    auth: authReducer,
    job: jobReducer,
    sources: sourcesReducer,
    ui: uiReducer,
    sync: syncReducer,
    library: libraryReducer,
  },
})
