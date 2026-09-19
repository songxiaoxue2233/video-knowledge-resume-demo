import { createSSRApp } from 'vue'
import { createPinia } from 'pinia'
import uviewPlus from 'uview-plus'
import App from './App.vue'
import './uni.scss'
import './permission.js'

export function createApp() {
  const app = createSSRApp(App)

  // uView-plus 组件库入口。当前页面以原生 uni 组件为主，保留 uView 能力用于后续表单、弹窗、Toast 替换。
  app.use(uviewPlus)
  app.use(createPinia())

  return {
    app
  }
}
