<template>
  <view class="page">
    <AppNavBar title="会员套餐">
      <template #left><IconButton icon="‹" @click="goBack" /></template>
    </AppNavBar>

    <view class="content">
      <view v-if="!paymentConfig.enabled" class="card section-card beta-card">
        <view class="beta-title">免费内测进行中</view>
        <view class="beta-desc">暂不开放付费，注册用户可免费获得 {{ paymentConfig.freeBetaQuota || 20 }} 次解析额度。</view>
      </view>
      <view v-for="plan in displayPlans" :key="plan.id" class="card section-card plan-card">
        <view>
          <view class="plan-name">{{ plan.name }}</view>
          <view class="plan-desc">{{ plan.desc }}</view>
        </view>
        <view class="price">{{ plan.price }}</view>
        <view class="primary-btn buy-btn" :class="{ disabled: paying || plan.id === 'free' }" @tap="buy(plan.id)">
          {{ plan.id === 'free' ? '当前基础套餐' : paying ? '正在创建支付订单' : '微信支付开通' }}
        </view>
      </view>
      <view v-if="paymentConfig.enabled" class="payment-tip">
        支付结果以微信支付服务器查单与回调为准。付款成功后额度会自动到账。
      </view>
      <view v-if="paymentConfig.enabled && recentOrders.length" class="card section-card order-card">
        <view class="order-heading">最近订单</view>
        <view v-for="order in recentOrders" :key="order.outTradeNo" class="order-row">
          <view>
            <view class="order-name">{{ order.planName }}</view>
            <view class="order-time">{{ formatCompactTime(order.paidAt || order.createdAt) }}</view>
          </view>
          <view class="order-result">
            <view class="order-amount">¥{{ (order.amount / 100).toFixed(2) }}</view>
            <view class="order-status" :class="{ paid: order.status === 'SUCCESS' }">
              {{ orderStatusText(order.status) }}
            </view>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AppNavBar from '@/components/AppNavBar.vue'
import IconButton from '@/components/IconButton.vue'
import { api } from '@/common/api.js'
import { formatCompactTime } from '@/common/text.js'
import { useUserStore } from '@/store/user.js'

const user = useUserStore()
const paying = ref(false)
const paymentConfig = ref({ enabled: false, freeBeta: true, freeBetaQuota: 20, mpWeixinConfigured: false, appConfigured: false })
const recentOrders = ref([])
const plans = [
  { id: 'free', name: '免费内测版', price: '¥0', desc: '无需支付，内测期间免费使用' },
  { id: 'monthly', name: '月度VIP', price: '¥29/月', desc: '每月300次解析，适合高频学习' },
  { id: 'yearly', name: '年度VIP', price: '¥199/年', desc: '每年5000次解析，适合重度知识库用户' }
]
const displayPlans = computed(() => paymentConfig.value.enabled ? plans : plans.filter((plan) => plan.id === 'free'))

function goBack() {
  uni.navigateBack()
}

function buy(plan) {
  if (!paymentConfig.value.enabled || plan === 'free' || paying.value) return
  // #ifdef H5
  uni.showModal({
    title: '请在微信小程序或 App 内支付',
    content: 'H5 页面不直接收集付款信息，请打开微信小程序或安装 App 后完成微信支付。',
    showCancel: false
  })
  return
  // #endif

  // #ifdef MP-WEIXIN
  if (!paymentConfig.value.mpWeixinConfigured) return paymentNotConfigured()
  paying.value = true
  uni.login({
    provider: 'weixin',
    success: (login) => createAndPay(plan, 'mp-weixin', login.code),
    fail: () => finishWithError('获取微信登录凭证失败')
  })
  // #endif

  // #ifdef APP-PLUS
  if (uni.getSystemInfoSync().platform === 'ios') {
    uni.showModal({
      title: 'iOS 会员支付暂未开放',
      content: '数字会员在 iOS 上需要接入 Apple 应用内购买，不能使用微信支付绕过 App Store。',
      showCancel: false
    })
    return
  }
  if (!paymentConfig.value.appConfigured) return paymentNotConfigured()
  paying.value = true
  createAndPay(plan, 'app')
  // #endif
}

function createAndPay(plan, channel, loginCode = '') {
  uni.showLoading({ title: '创建支付订单' })
  api.createPaymentOrder({ plan, channel, loginCode })
    .then((order) => {
      uni.hideLoading()
      if (channel === 'mp-weixin') {
        uni.requestPayment({
          provider: 'wxpay',
          ...order.clientParams,
          success: () => confirmPayment(order.outTradeNo),
          fail: (error) => finishWithError(error?.errMsg?.includes('cancel') ? '已取消支付' : '微信支付未完成')
        })
      } else {
        uni.requestPayment({
          provider: 'wxpay',
          orderInfo: order.clientParams,
          success: () => confirmPayment(order.outTradeNo),
          fail: (error) => finishWithError(error?.errMsg?.includes('cancel') ? '已取消支付' : '微信支付未完成')
        })
      }
    })
    .catch(() => {
      paying.value = false
      uni.hideLoading()
    })
}

function confirmPayment(outTradeNo, attempt = 0) {
  uni.showLoading({ title: '正在确认到账' })
  api.paymentOrder(outTradeNo)
    .then((order) => {
      if (order.status === 'SUCCESS') {
        return api.me().then((me) => {
          user.setQuota(me)
          loadOrders()
          paying.value = false
          uni.hideLoading()
          uni.showToast({ title: '支付成功，会员已开通', icon: 'success' })
        })
      }
      if (attempt < 7) {
        setTimeout(() => confirmPayment(outTradeNo, attempt + 1), 1500)
      } else {
        paying.value = false
        uni.hideLoading()
        uni.showModal({
          title: '支付结果确认中',
          content: '微信可能正在延迟通知，稍后重新进入此页面即可刷新会员状态。',
          showCancel: false
        })
      }
    })
    .catch(() => {
      paying.value = false
      uni.hideLoading()
    })
}

function finishWithError(title) {
  paying.value = false
  uni.hideLoading()
  uni.showToast({ title, icon: 'none' })
}

function paymentNotConfigured() {
  const missing = [
    ...(paymentConfig.value.missing?.mpWeixin || []),
    ...(paymentConfig.value.missing?.app || [])
  ]
  const invalid = [
    ...(paymentConfig.value.invalid?.mpWeixin || []),
    ...(paymentConfig.value.invalid?.app || [])
  ]
  const detail = [...new Set([...missing, ...invalid])]
  uni.showModal({
    title: '微信支付尚未配置',
    content: detail.length ? `缺少或无效：${detail.join('、')}` : '需要先配置微信支付商户资料和对应 AppID。',
    showCancel: false
  })
}

function orderStatusText(status) {
  const labels = {
    SUCCESS: '已支付',
    NOTPAY: '待支付',
    USERPAYING: '支付处理中',
    CLOSED: '已关闭',
    REVOKED: '已撤销',
    PAYERROR: '支付失败',
    CREATE_FAILED: '下单失败',
    CREATING: '正在创建'
  }
  return labels[status] || status || '待支付'
}

function loadOrders() {
  api.paymentOrders()
    .then((res) => {
      recentOrders.value = res.items || []
    })
    .catch(() => {})
}

onShow(() => {
  api.paymentConfig()
    .then((res) => {
      paymentConfig.value = res
      if (res.enabled) loadOrders()
    })
    .catch(() => {})
})
</script>

<style scoped lang="scss">
.plan-card {
  display: grid;
  gap: 12px;
}
.beta-card {
  margin-bottom: 16px;
  background: linear-gradient(135deg, #ecfdf3, #f4fff8);
  border: 1px solid #b7ebc9;
}
.beta-title {
  color: #238653;
  font-size: 18px;
  font-weight: 900;
}
.beta-desc {
  margin-top: 8px;
  color: #4f7560;
  font-size: 13px;
  line-height: 1.7;
}
.plan-name {
  color: #222222;
  font-size: 18px;
  font-weight: 900;
}
.plan-desc {
  margin-top: 6px;
  color: #888888;
  font-size: 12px;
}
.price {
  color: #38A169;
  font-size: 24px;
  font-weight: 900;
}
.buy-btn {
  width: 100%;
}
.buy-btn.disabled {
  opacity: .55;
}
.payment-tip {
  margin-top: 18px;
  color: #888;
  text-align: center;
  font-size: 12px;
  line-height: 1.6;
}
.order-card {
  margin-top: 16px;
}
.order-heading {
  margin-bottom: 6px;
  color: #222;
  font-size: 16px;
  font-weight: 800;
}
.order-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}
.order-row:last-child {
  border-bottom: 0;
}
.order-name,
.order-amount {
  color: #333;
  font-weight: 700;
}
.order-time,
.order-status {
  margin-top: 4px;
  color: #999;
  font-size: 11px;
}
.order-result {
  text-align: right;
}
.order-status.paid {
  color: #38A169;
}
</style>
