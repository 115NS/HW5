/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The dashboard calls the FastAPI backend directly at VITE_API_BASE (default http://localhost:8000),
// which allows this dev origin (http://localhost:5173) through CORS. See src/api.ts.
export default defineConfig({
  plugins: [react()],
  // 5173 is preferred; if it is taken Vite uses the next free port (the backend allows 5173-5179).
  server: { port: 5173 },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
