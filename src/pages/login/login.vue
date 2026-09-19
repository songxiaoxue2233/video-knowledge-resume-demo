<template>
  <view class="phone-page auth-page">
    <view class="brand">
      <view class="brand-mark"><VKIcon name="sparkle" :size="30" /></view>
      <view class="brand-title">刷到的都是自己的</view>
      <view class="brand-desc">把刷到的视频内容，沉淀成自己的知识库</view>
    </view>

    <view class="auth-card">
      <view class="card-title">欢迎回来</view>
      <view class="card-desc">登录后继续整理你的知识笔记</view>

      <view class="field">
        <text>手机号</text>
        <input v-model="phone" type="number" maxlength="11" placeholder="请输入 11 位手机号" />
      </view>
      <view class="field">
        <text>密码</text>
        <input v-model="password" password placeholder="请输入密码" />
      </view>

      <view class="primary-button" :class="{ disabled: loading }" @tap="submit">
        {{ loading ? '登录中...' : '登录' }}
      </view>
      <view class="tip-row">
        <text>没有账号？</text>
        <text class="link" @tap="goRegister">去注册</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { api } from '@/common/api.js'
import { useUserStore } from '@/store/user.js'
import VKIcon from '@/components/VKIcon.vue'

const phone = ref('')
const password = ref('')
const loading = ref(false)
const store = useUserStore()

function validPhone(value) {
  return /^\d{11}$/.test(value)
}

function submit() {
  if (loading.value) return
  if (!validPhone(phone.value)) {
    uni.showToast({ title: '手机号必须为 11 位数字', icon: 'none' })
    return
  }
  if (!password.value) {
    uni.showToast({ title: '密码不可为空', icon: 'none' })
    return
  }
  loading.value = true
  api.login({ phone: phone.value, password: password.value })
    .then((res) => {
      store.setSession(res)
      uni.reLaunch({ url: '/pages/dashboard/index' })
    })
    .finally(() => {
      loading.value = false
    })
}

function goRegister() {
  uni.navigateTo({ url: '/pages/register/register' })
}
</script>

<style scoped lang="scss">
.auth-page {
  padding-bottom: 36px;
  background:
    radial-gradient(circle at 20px 88px, rgba(255,120,183,.14), transparent 132px),
    radial-gradient(circle at 95% 72px, rgba(108,76,245,.16), transparent 130px),
    #fff;
}
.brand {
  margin-top: 22px;
}
.brand-mark {
  width: 66px;
  height: 66px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 22px;
  color: #fff;
  background: linear-gradient(135deg, #8c6cff 0%, #c19bff 100%);
  box-shadow: 0 18px 34px rgba(108,76,245,.22);
}
.brand-title {
  margin-top: 24px;
  color: #161616;
  font-size: 28px;
  font-weight: 950;
  line-height: 1.25;
}
.brand-desc {
  margin-top: 8px;
  color: #85818d;
  font-size: 14px;
  font-weight: 700;
}
.auth-card {
  margin-top: 34px;
  padding: 22px 18px;
  border: 1px solid #eceaf1;
  border-radius: 24px;
  background: rgba(255,255,255,.9);
  box-shadow: 0 18px 36px rgba(33,7,95,.08);
}
.card-title {
  color: #161616;
  font-size: 22px;
  font-weight: 950;
}
.card-desc {
  margin-top: 6px;
  color: #85818d;
  font-size: 13px;
  font-weight: 700;
}
.field {
  margin-top: 16px;
}
.field text {
  color: #161616;
  font-size: 13px;
  font-weight: 900;
}
.field input {
  height: 52px;
  margin-top: 8px;
  padding: 0 16px;
  border: 1px solid #eceaf1;
  border-radius: 16px;
  color: #161616;
  background: #f8f7fc;
  font-size: 15px;
  box-sizing: border-box;
}
.primary-button {
  margin-top: 22px;
}
.tip-row {
  display: flex;
  justify-content: center;
  gap: 4px;
  margin-top: 18px;
  color: #85818d;
  font-size: 14px;
  font-weight: 800;
}
.tip-row .link {
  color: #6c4cf5;
}
</style>
