import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// Vite dev server. Two LAN-friendly knobs:
//  - host: '0.0.0.0' so iPads on the same network can hit the dev server
//  - server.proxy target reads VITE_API_URL so the same React build can
//    point at localhost (default) or the Mac's LAN IP for iPad demos.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_API_URL || 'http://localhost:5001'
  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0',
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
