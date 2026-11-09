import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The API runs on :8000 in development; the browser only ever calls /api on its own origin.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:8000' } },
})
