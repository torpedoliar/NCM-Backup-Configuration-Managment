import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8443',
      '/ws': { target: 'ws://127.0.0.1:8443', ws: true },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          recharts: ['recharts'],
          react: ['react', 'react-dom', 'wouter', '@tanstack/react-query', 'zustand', 'axios'],
        },
      },
    },
  },
  test: {
    setupFiles: ['./src/test/setup.ts'],
    environment: 'jsdom',
  },
});
