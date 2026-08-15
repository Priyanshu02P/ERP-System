import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The FastAPI backend serves product images from /assets (mounted from
// frontend/assets/products). Vite's own build output must not collide with
// that path, so JS/CSS bundles are emitted under /app/ instead of /assets/.
export default defineConfig({
  plugins: [react()],
  base: '/',
  build: {
    outDir: '../dist',
    emptyOutDir: true,
    assetsDir: 'app',
  },
  server: {
    port: 5173,
    proxy: {
      '/api/v1': 'http://localhost:8000',
      '/assets': 'http://localhost:8000',
    },
  },
})
