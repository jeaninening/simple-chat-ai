import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import svgLoader from 'vite-svg-loader'

export default defineConfig({
  plugins: [vue(), svgLoader()],
  base: './',  // ✅ 相对路径，适合部署在任意路径
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/v1': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  },
  // 👇 添加 build 配置，确保构建产物正确
  build: {
    outDir: 'dist',  // 输出目录，默认就是 dist
    assetsDir: 'assets',  // 静态资源目录
    sourcemap: false,  // 生产环境建议关闭
    rollupOptions: {
      output: {
        // 确保文件命名一致
        chunkFileNames: 'assets/js/[name]-[hash].js',
        entryFileNames: 'assets/js/[name]-[hash].js',
        assetFileNames: 'assets/[ext]/[name]-[hash].[ext]'
      }
    }
  }
})