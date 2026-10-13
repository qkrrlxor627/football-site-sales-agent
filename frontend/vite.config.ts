import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

// 개발 중에는 Vite(5173)가 화면을, FastAPI(8000)가 API와 상품 사진을 맡는다.
const backend = process.env.PITCHROOM_API ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: { '/api': backend, '/images': backend },
  },
  build: { outDir: 'dist', emptyOutDir: true },
  test: { environment: 'jsdom', include: ['tests/**/*.test.ts'] },
})
