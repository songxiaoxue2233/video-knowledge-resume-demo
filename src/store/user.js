import { defineStore } from 'pinia'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: uni.getStorageSync('token') || '',
    phone: uni.getStorageSync('phone') || '',
    memberType: uni.getStorageSync('memberType') || '普通用户',
    todayParseCount: Number(uni.getStorageSync('todayParseCount') || 0),
    remainingParseCount: Number(uni.getStorageSync('remainingParseCount') || 0)
  }),
  getters: {
    isLogin: (state) => Boolean(state.token)
  },
  actions: {
    setSession(payload) {
      this.token = payload.token
      this.phone = payload.phone
      this.memberType = payload.memberType || '普通用户'
      this.todayParseCount = payload.todayParseCount || 0
      this.remainingParseCount = payload.remainingParseCount || 0
      uni.setStorageSync('token', this.token)
      uni.setStorageSync('phone', this.phone)
      uni.setStorageSync('memberType', this.memberType)
      uni.setStorageSync('todayParseCount', this.todayParseCount)
      uni.setStorageSync('remainingParseCount', this.remainingParseCount)
    },
    setQuota(payload) {
      this.memberType = payload.memberType || this.memberType
      this.todayParseCount = payload.todayParseCount ?? this.todayParseCount
      this.remainingParseCount = payload.remainingParseCount ?? this.remainingParseCount
      uni.setStorageSync('memberType', this.memberType)
      uni.setStorageSync('todayParseCount', this.todayParseCount)
      uni.setStorageSync('remainingParseCount', this.remainingParseCount)
    },
    logout() {
      this.token = ''
      this.phone = ''
      this.memberType = '普通用户'
      this.todayParseCount = 0
      this.remainingParseCount = 0
      uni.removeStorageSync('token')
      uni.removeStorageSync('phone')
      uni.removeStorageSync('memberType')
      uni.removeStorageSync('todayParseCount')
      uni.removeStorageSync('remainingParseCount')
    }
  }
})
