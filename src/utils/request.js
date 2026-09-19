import { API_BASE_URL } from '@/config.js'
import { useUserStore } from '@/store/user.js'

export function request(path, options = {}) {
  const store = useUserStore()
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${API_BASE_URL}${path}`,
      method: options.method || 'GET',
      data: options.data || {},
      header: {
        'Content-Type': 'application/json',
        ...(store.token ? { Authorization: `Bearer ${store.token}` } : {})
      },
      success(res) {
        if (res.statusCode === 401) {
          store.logout()
          uni.showToast({ title: '登录已失效，请重新登录', icon: 'none' })
          uni.reLaunch({ url: '/pages/login/login' })
          reject(new Error('unauthorized'))
          return
        }
        if (res.statusCode === 429) {
          uni.showToast({ title: '请求过快，请稍后再试', icon: 'none' })
          reject(new Error('rate limited'))
          return
        }
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
        } else {
          const message = (res.data && (res.data.message || res.data.error)) || '接口请求失败'
          uni.showToast({ title: message, icon: 'none' })
          reject(new Error(message))
        }
      },
      fail(error) {
        uni.showToast({ title: '网络异常，请稍后重试', icon: 'none' })
        reject(error)
      }
    })
  })
}
