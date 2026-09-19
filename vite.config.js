import { defineConfig } from 'vite'
import uniModule from '@dcloudio/vite-plugin-uni'

const uni = typeof uniModule === 'function' ? uniModule : uniModule.default

// UniApp 官方 Vite 配置入口，HBuilderX / CLI 都会读取该文件。
export default defineConfig({
  plugins: [uni()]
})
