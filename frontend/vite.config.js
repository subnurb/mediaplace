import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const certsDir = resolve(import.meta.dirname, 'certs')

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    https: {
      key:  readFileSync(resolve(certsDir, 'key.pem')),
      cert: readFileSync(resolve(certsDir, 'cert.pem')),
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        credentials: true,
      },
    },
  },
})
