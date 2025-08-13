import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // (dev server is optional once you build; keep if you still use it)
  server: {
    port: 5173
  },
  build: {
    outDir: '../backend/static', // << build into the backend
    emptyOutDir: true
  }
})
