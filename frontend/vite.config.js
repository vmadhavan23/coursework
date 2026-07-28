import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev-server proxy so the frontend can call a same-origin `/api/*` path and
// never needs to know the backend's real host/port (or deal with CORS) —
// keeps the backend's own API surface exactly as described in openapi.yaml.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
