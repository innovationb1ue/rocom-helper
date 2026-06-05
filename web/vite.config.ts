import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 18732,
    proxy: {
      '/api': 'http://localhost:18731',
      '/ws': { target: 'ws://localhost:18731', ws: true },
    },
  },
})
