import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import https from 'node:https'

const certsDir = resolve(import.meta.dirname, 'certs')

export default defineConfig(({ mode }) => {
  // Load .env from frontend dir (config location), not cwd, so it works when run from project root
  const envDir = import.meta.dirname
  const env = loadEnv(mode, envDir, '')
  const apiTarget = env.VITE_API_TARGET || 'http://localhost:8000'
  const isHttpsBackend = apiTarget.startsWith('https://')

  // For HTTPS backend (runsslserver), use an agent that accepts self-signed certs
  const httpsAgent = isHttpsBackend
    ? new https.Agent({ rejectUnauthorized: false })
    : undefined

  return {
    plugins: [react()],
    server: {
      port: 5173,
      https: {
        key:  readFileSync(resolve(certsDir, 'key.pem')),
        cert: readFileSync(resolve(certsDir, 'cert.pem')),
      },
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          credentials: true,
          ...(isHttpsBackend
            ? { secure: false, agent: httpsAgent }
            : {}),
        },
      },
    },
  }
})
