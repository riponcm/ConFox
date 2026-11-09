import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  // One .env at the repo root serves both halves; only VITE_* values reach the browser bundle.
  // loadEnv with an empty prefix reads API_PORT too (config only; it is never exposed to the browser).
  const env = { ...loadEnv(mode, '..', ''), ...process.env }
  return {
    plugins: [react()],
    envDir: '..',
    // The browser only ever calls /api on its own origin; in development that is proxied to the API
    // (port 8000 unless API_PORT says otherwise, so several checkouts can run side by side).
    server: { proxy: { '/api': `http://localhost:${env.API_PORT || 8000}` } },
  }
})
