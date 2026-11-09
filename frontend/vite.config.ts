import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  // One .env at the repo root serves both halves; only VITE_* values reach the browser bundle.
  envDir: '..',
  // The API runs on :8000 in development; the browser only ever calls /api on its own origin.
  server: { proxy: { '/api': 'http://localhost:8000' } },
})
