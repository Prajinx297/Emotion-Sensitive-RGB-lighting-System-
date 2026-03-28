import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:5000',
      '/video_feed': 'http://localhost:5000',
      '/api/frame': 'http://localhost:5000'
    }
  }
});
