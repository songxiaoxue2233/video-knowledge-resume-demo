<template>
  <view class="phone-page auth-page">
    <view class="nav-line">
      <view class="icon-button" @tap="goLogin"><VKIcon name="back" :size="21" /></view>
      <text class="page-title">注册账号</text>
      <view></view>
    </view>

    <view class="hero-card">
      <view class="hero-icon"><VKIcon name="book" :size="30" /></view>
      <view>
      <view class="hero-title">创建你的个人知识库</view>
        <view class="hero-desc">多端同步，独立沉淀，长期复盘</view>
      </view>
    </view>

    <view class="auth-card">
      <view class="field">
        <text>手机号</text>
        <input v-model="phone" type="number" maxlength="11" placeholder="请输入 11 位手机号" />
      </view>
      <view class="field">
        <text>设置密码</text>
        <input v-model="password" password placeholder="6-20 位，需包含字母和数字" />
      </view>
      <view class="field">
        <text>确认密码</text>
        <input v-model="confirmPassword" password placeholder="请再次输入密码" />
      </view>

      <view class="primary-button" :class="{ disabled: loading }" @tap="submit">
        {{ loading ? '注册中...' : '注册' }}
      </view>
      <view class="tip-row">
        <text>已有账号？</text>
        <text class="link" @tap="goLogin">去登录</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { api } from '@/common/api.js'
import VKIcon from '@/components/VKIcon.vue'

const phone = ref('')
const password = ref('')
const confirmPassword = ref('')
const loading = ref(false)

function validate() {
  if (!/^\d{11}$/.test(phone.value)) return '手机号必须为 11 位有效数字'
  if (!/^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d\S]{6,20}$/.test(password.value)) return '密码需 6-20 位，且不能纯数字或纯字母'
  if (password.value !== confirmPassword.value) return '两次输入密码不一致'
  return ''
}

function submit() {
  if (loading.value) return
  const message = validate()
  if (message) {
    uni.showToast({ title: message, icon: 'none' })
    return
  }
  loading.value = true
  api.register({ phone: phone.value, password: password.value })
    .then(() => {
      uni.showModal({
        title: '注册成功',
        content: '请使用手机号和密码登录。',
        showCancel: false,
        success: () => uni.redirectTo({ url: '/pages/login/login' })
      })
    })
    .finally(() => {
      loading.value = false
    })
}

function goLogin() {
  uni.redirectTo({ url: '/pages/login/login' })
}
</script>

<style scoped lang="scss">
.auth-page {
  padding-bottom: 36px;
  background:
    radial-gradient(circle at 12% 106px, rgba(108,76,245,.14), transparent 132px),
    radial-gradient(circle at 88% 88px, rgba(108,202,244,.16), transparent 130px),
    #fff;
}
.nav-line {
  display: grid;
  grid-template-columns: 44px 1fr 44px;
  align-items: center;
}
.nav-line .page-title {
  text-align: center;
}
.hero-card {
  margin-top: 28px;
  padding: 20px;
  display: flex;
  gap: 16px;
  align-items: center;
  border-radius: 24px;
  color: #fff;
  background: linear-gradient(135deg, #8c6cff 0%, #c19bff 100%);
  box-shadow: 0 18px 36px rgba(108,76,245,.20);
}
.hero-icon {
  width: 62px;
  height: 62px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: 22px;
  background: rgba(255,255,255,.22);
}
.hero-title {
  font-size: 22px;
  font-weight: 950;
}
.hero-desc {
  margin-top: 7px;
  font-size: 13px;
  opacity: .88;
}
.auth-card {
  margin-top: 18px;
  padding: 22px 18px;
  border: 1px solid #eceaf1;
  border-radius: 24px;
  background: #fff;
  box-shadow: 0 18px 36px rgba(33,7,95,.08);
}
.field {
  margin-top: 16px;
}
.field:first-child {
  margin-top: 0;
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
