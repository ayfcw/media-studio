import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 开发服务器：把 /api 请求代理到网关，避免跨域
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '127.0.0.1',
    proxy: {
      '/api': { target: 'http://127.0.0.1:8200', changeOrigin: true },
    },
  },
})
