const WHITE_LIST = ['/pages/login/login', '/pages/register/register']

function hasToken() {
  return Boolean(uni.getStorageSync('token'))
}

function guard(url) {
  const path = url.split('?')[0]
  if (WHITE_LIST.includes(path) || hasToken()) return true
  uni.reLaunch({ url: '/pages/login/login' })
  return false
}

;['navigateTo', 'redirectTo', 'reLaunch', 'switchTab'].forEach((method) => {
  uni.addInterceptor(method, {
    invoke(args) {
      return guard(args.url)
    }
  })
})
