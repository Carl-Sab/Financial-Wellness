import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Forwards /api/* to the FastAPI backend (see backend/README, run on
    // :8000) so pages can just fetch("/api/v1/...") same-origin — no CORS
    // config needed, and no separate API_BASE_URL to keep in sync.
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
