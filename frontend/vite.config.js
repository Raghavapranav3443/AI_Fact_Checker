import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,        // fail loudly if port is taken — no silent port changes
    host: '127.0.0.1',       // bind localhost only — not 0.0.0.0
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
        // SSE-specific: disable response buffering so events stream immediately
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            // Force chunked transfer for SSE
            if (proxyRes.headers['content-type']?.includes('text/event-stream')) {
              proxyRes.headers['x-accel-buffering'] = 'no'
              proxyRes.headers['cache-control'] = 'no-cache'
            }
          })
        },
      }
    }
  },
  preview: {
    port: 5173,
    strictPort: true,
    host: '127.0.0.1',
  },
  build: {
    sourcemap: false,        // no sourcemaps in production build — don't expose code
    rollupOptions: {
      output: {
        // Predictable chunk names — easier to cache-bust in production
        manualChunks: {
          vendor: ['react', 'react-dom'],
          axios:  ['axios'],
        }
      }
    }
  }
})
