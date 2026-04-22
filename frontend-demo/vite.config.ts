import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig(() => {
  return {
    plugins: [react()],
    optimizeDeps: {
      exclude: ['lucide-react'],
    },
    server: {
      port: 5173,
      strictPort: true, // 🚀 报错就停下，不准换 5174
      host: "0.0.0.0",
      allowedHosts: ['soundverse.vbegin.com.cn', 'localhost', '127.0.0.1'],
      proxy: {
        '/api': {
          target: 'http://soundverse-api:8000',
          changeOrigin: true,
        },
      },
      // Windows + Docker 环境下启用 polling 以支持热重载
      watch: {
        usePolling: true,
        interval: 1000,
      },
    },
  };
});
