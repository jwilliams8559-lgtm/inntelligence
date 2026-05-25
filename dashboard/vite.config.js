import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// React dev server on 5173; all /api/* requests are proxied to the Flask API on
// 5001 so the browser only ever talks to one origin (no CORS).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: 'http://localhost:5001', changeOrigin: true },
    },
  },
})
