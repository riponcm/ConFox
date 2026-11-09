import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  // One .env at the repo root serves both halves; only VITE_* values reach the browser bundle.
  envDir: '..',
  // The browser only ever calls /api on its own origin; in development that is proxied to the API
  // (port 8000 unless API_PORT says otherwise, so several checkouts can run side by side).
  server: { proxy: { '/api': `http://localhost:${process.env.API_PORT ?? 8000}` } },
})
