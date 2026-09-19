<template>
  <view class="phone-page mine-page">
    <text class="page-title">我的</text>

    <view class="user-card">
      <view class="user-row">
        <view class="avatar-big"><VKIcon name="sparkle" :size="26" /></view>
        <view class="user-info">
          <view class="user-name">{{ displayName }}</view>
          <view class="user-type">{{ memberType }}</view>
        </view>
        <view class="vip-btn" @tap="goVip">升级会员</view>
      </view>
      <view class="data-row">
        <view><text>笔记</text><strong>{{ noteCount }}</strong></view>
        <view><text>剩余额度</text><strong>{{ remaining }}</strong></view>
      </view>
    </view>

    <view class="menu-card card">
      <view v-for="item in menus" :key="item.title" class="menu-item" @tap="handleMenu(item.key)">
        <view class="menu-left">
          <view class="menu-icon"><VKIcon :name="item.icon" :size="21" /></view>
          <text>{{ item.title }}</text>
        </view>
        <view class="menu-right">
          <text v-if="item.extra">{{ item.extra }}</text>
          <VKIcon name="chevron" :size="17" />
        </view>
      </view>
    </view>

    <view class="section-head">
      <text class="section-title">同步与本地导出</text>
      <text class="refresh" @tap="loadIntegrations">刷新状态</text>
    </view>
    <view class="integration-list">
      <view v-for="item in integrationItems" :key="item.key" class="integration-card card">
        <view class="integration-logo">{{ item.short }}</view>
        <view class="integration-info">
          <view class="integration-title">{{ item.title }}</view>
          <view class="integration-desc">{{ item.description }}</view>
        </view>
        <view
          class="integration-action"
          :class="{ connected: item.authorized, disabled: !item.configured }"
          @tap="item.authorized ? disconnectProvider(item.key) : connectProvider(item)"
        >
          {{ item.authorized ? '已连接' : item.configured ? '去授权' : '待配置' }}
        </view>
      </view>
    </view>

    <view class="section-head">
      <text class="section-title">导出记录</text>
      <text class="refresh" @tap="loadExports">刷新</text>
    </view>
    <view v-if="exportRecords.length === 0" class="empty-export">
      <VKIcon name="book" :size="24" />
      <text>暂无导出记录</text>
    </view>
    <view v-else class="export-list">
      <view v-for="item in exportRecords" :key="item.id" class="export-item card" @tap="openRecord(item)">
        <view class="export-icon"><VKIcon name="book" :size="20" /></view>
        <view class="export-info">
          <view class="export-name">{{ item.filename }}</view>
          <view class="export-meta">{{ kindName(item.kind) }} · {{ item.note_count }} 条 · {{ formatCompactTime(item.created_at) }}</view>
        </view>
        <VKIcon name="chevron" :size="17" />
      </view>
    </view>

    <view class="logout" @tap="logout">退出登录</view>
    <FloatingTabBar active="mine" />
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import FloatingTabBar from '@/components/FloatingTabBar.vue'
import VKIcon from '@/components/VKIcon.vue'
import { api } from '@/common/api.js'
import { openDownload, toast } from '@/common/actions.js'
import { formatCompactTime } from '@/common/text.js'
import { useUserStore } from '@/store/user.js'

const store = useUserStore()
const noteCount = ref(0)
const exportRecords = ref([])
const integrations = ref({
  feishu: { configured: false, authorized: false },
  hints: {}
})

const displayName = computed(() => store.phone || '未登录用户')
const memberType = computed(() => store.memberType || '普通用户')
const remaining = computed(() => store.remainingParseCount || 0)
const integrationItems = computed(() => [
  {
    key: 'feishu',
    short: '飞',
    title: '飞书云空间',
    description: integrations.value.feishu?.authorized
      ? '已授权，可在知识库或笔记详情中同步'
      : integrations.value.feishu?.configured ? '授权后可同步 Markdown 笔记' : '需要先配置飞书开放平台应用',
    ...integrations.value.feishu
  }
])
const menus = computed(() => [
  { key: 'account', title: '账号与安全', icon: 'shield' },
  { key: 'quota', title: '解析额度', icon: 'zap', extra: `剩余 ${remaining.value} 次` },
  { key: 'export', title: '导出记录', icon: 'book', extra: `${exportRecords.value.length} 条` },
  { key: 'about', title: '关于我们', icon: 'info' }
])

onShow(() => {
  loadUser()
  loadExports()
  loadIntegrations()
})

function loadUser() {
  api.me()
    .then((res) => store.setQuota(res))
    .catch(() => {})
  api.dashboard()
    .then((res) => {
      noteCount.value = res?.stats?.totalNotes || 0
    })
    .catch(() => {
      noteCount.value = 0
    })
}

function loadExports() {
  api.exportRecords()
    .then((res) => {
      exportRecords.value = (res.items || []).slice(0, 5)
    })
    .catch(() => {
      exportRecords.value = []
    })
}

function loadIntegrations() {
  api.integrationStatus()
    .then((res) => {
      integrations.value = res
    })
    .catch(() => {})
}

function connectProvider(item) {
  if (!item.configured) return toast(`${item.title}尚未完成后台配置`)
  uni.showLoading({ title: '正在获取授权地址' })
  api.integrationAuthUrl(item.key)
    .then((res) => {
      uni.hideLoading()
      // #ifdef H5
      window.location.href = res.url
      // #endif
      // #ifndef H5
      uni.navigateTo({ url: `/pages/oauth/webview?provider=${item.key}&url=${encodeURIComponent(res.url)}` })
      // #endif
    })
    .catch(() => uni.hideLoading())
}

function disconnectProvider(provider) {
  uni.showModal({
    title: '解除云文档授权',
    content: '解除后需要重新授权才能继续同步，已导出的文件不会删除。',
    success: (res) => {
      if (!res.confirm) return
      api.disconnectIntegration(provider)
        .then(() => {
          toast('已解除授权')
          loadIntegrations()
        })
    }
  })
}

function kindName(kind) {
  return { word: 'Word', markdown: 'Markdown', feishu: '飞书' }[kind] || kind || '文件'
}

function openRecord(item) {
  openDownload(item, '导出文件')
}

function handleMenu(key) {
  if (key === 'quota') return goVip()
  if (key === 'export') return loadExports()
  toast('功能已预留')
}

function goVip() {
  uni.navigateTo({ url: '/pages/vip/vip' })
}

function logout() {
  uni.showModal({
    title: '确认退出',
    content: '退出后将返回登录页',
    success: (res) => {
      if (res.confirm) {
        store.logout()
        uni.reLaunch({ url: '/pages/login/login' })
      }
    }
  })
}
</script>

<style scoped lang="scss">
.mine-page {
  background:
    radial-gradient(circle at 90% 96px, rgba(108,76,245,.12), transparent 120px),
    #fff;
}
.user-card {
  margin-top: 22px;
  padding: 20px 18px 16px;
  border: 1px solid #e3ddfb;
  border-radius: 20px;
  background: linear-gradient(135deg, #f1ebff 0%, #fbf8ff 100%);
  box-shadow: 0 16px 30px rgba(33,7,95,.06);
}
.user-row {
  display: flex;
  align-items: center;
  gap: 14px;
}
.avatar-big {
  width: 66px;
  height: 66px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: #6c4cf5;
  background: #fff;
}
.user-info { flex: 1; min-width: 0; }
.user-name {
  color: #161616;
  font-size: 22px;
  font-weight: 950;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.user-type {
  margin-top: 6px;
  color: #85818d;
  font-size: 13px;
  font-weight: 700;
}
.vip-btn {
  height: 42px;
  padding: 0 16px;
  display: flex;
  align-items: center;
  border-radius: 21px;
  color: #fff;
  background: #21075f;
  font-size: 14px;
  font-weight: 900;
}
.data-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  margin-top: 22px;
  padding: 14px 0;
  border: 1px solid #e9e3fb;
  border-radius: 14px;
  background: rgba(255,255,255,.6);
}
.data-row view {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.data-row text {
  color: #6c4cf5;
  font-size: 13px;
  font-weight: 800;
}
.data-row strong {
  color: #6c4cf5;
  font-size: 22px;
  font-weight: 950;
}
.menu-card {
  margin-top: 24px;
  overflow: hidden;
}
.menu-item {
  min-height: 62px;
  padding: 0 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #eceaf1;
}
.menu-item:last-child { border-bottom: 0; }
.menu-left,
.menu-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.menu-left text {
  color: #161616;
  font-size: 15px;
  font-weight: 900;
}
.menu-right {
  color: #85818d;
  font-size: 13px;
}
.menu-icon,
.export-icon {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: #6c4cf5;
  background: #f8f7fc;
}
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 24px 0 10px;
}
.refresh {
  color: #6c4cf5;
  font-size: 12px;
  font-weight: 900;
}
.integration-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.integration-card {
  min-height: 78px;
  padding: 14px;
  display: grid;
  grid-template-columns: 42px 1fr auto;
  align-items: center;
  gap: 12px;
}
.integration-logo {
  width: 42px;
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  color: #fff;
  background: #6c4cf5;
  font-size: 18px;
  font-weight: 950;
}
.integration-info { min-width: 0; }
.integration-title {
  color: #161616;
  font-size: 15px;
  font-weight: 900;
}
.integration-desc {
  margin-top: 4px;
  color: #85818d;
  font-size: 11px;
  font-weight: 700;
  line-height: 1.4;
}
.integration-action {
  padding: 8px 12px;
  border-radius: 999px;
  color: #fff;
  background: #6c4cf5;
  font-size: 12px;
  font-weight: 900;
}
.integration-action.connected {
  color: #1d925a;
  background: rgba(56,161,105,.14);
}
.integration-action.disabled {
  color: #85818d;
  background: #eceaf1;
}
.empty-export {
  min-height: 96px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border-radius: 20px;
  color: #85818d;
  background: #f8f7fc;
  font-size: 13px;
  font-weight: 800;
}
.export-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.export-item {
  min-height: 72px;
  padding: 12px;
  display: grid;
  grid-template-columns: 36px 1fr 18px;
  align-items: center;
  gap: 10px;
}
.export-info { min-width: 0; }
.export-name {
  color: #161616;
  font-size: 14px;
  font-weight: 900;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.export-meta {
  margin-top: 5px;
  color: #85818d;
  font-size: 12px;
  font-weight: 700;
}
.logout {
  height: 52px;
  margin-top: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 26px;
  color: #85818d;
  background: #f8f7fc;
  font-size: 15px;
  font-weight: 900;
}
</style>
