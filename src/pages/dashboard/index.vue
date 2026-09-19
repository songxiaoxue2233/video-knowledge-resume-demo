<template>
  <view class="phone-page home-page">
    <view class="top-row">
      <view class="hello">
        <view class="avatar"><VKIcon name="sparkle" :size="18" /></view>
        <view>
          <view class="hello-text">晚上好，晓雪</view>
          <view class="hello-sub">把短视频沉淀成可复用的知识</view>
        </view>
      </view>
    </view>

    <view class="quick-card" @tap="goImport">
      <view class="quick-icon"><VKIcon name="link" :size="22" /></view>
      <view class="quick-copy">
        <view class="quick-title">导入视频链接</view>
        <view class="quick-desc">支持抖音、小红书和多链接批量解析</view>
      </view>
      <view class="quick-arrow"><VKIcon name="arrow" :size="18" /></view>
    </view>

    <view class="section-head">
      <text class="section-title">最近导入</text>
      <view class="more-link" @tap="goLibrary">查看全部 <VKIcon name="chevron" :size="16" /></view>
    </view>
    <view v-if="recent.length === 0" class="empty-card">
      <VKIcon name="book" :size="26" />
      <text>暂无导入内容，先去粘贴一个视频链接吧。</text>
      <view class="empty-action" @tap="goImport">去导入</view>
    </view>
    <view v-else class="recent-list">
      <view v-for="item in recent" :key="item.id" class="recent-item card" @tap="goDetail(item.id)">
        <VideoThumb :duration="item.duration" :tone="item.tone" small />
        <view class="recent-info">
          <view class="recent-title line-clamp-2">{{ item.title }}</view>
          <view class="recent-meta">
            <PlatformLogo :type="item.platformType" />
            <text>{{ item.time }}</text>
          </view>
        </view>
        <view class="item-arrow"><VKIcon name="chevron" :size="18" /></view>
      </view>
    </view>

    <view class="progress-card">
      <view class="progress-head">
        <view class="progress-name"><VKIcon name="chart" :size="20" />本周知识进度</view>
        <view class="progress-count"><strong>{{ weekCount }}</strong><text>/ {{ weeklyGoal }} 条</text></view>
      </view>
      <view class="bar"><view class="bar-fill" :style="{ width: progressWidth }"></view></view>
      <view class="bar-meta">{{ progressHint }}</view>
    </view>

    <FloatingTabBar active="home" />
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import FloatingTabBar from '@/components/FloatingTabBar.vue'
import VKIcon from '@/components/VKIcon.vue'
import VideoThumb from '@/components/VideoThumb.vue'
import PlatformLogo from '@/components/PlatformLogo.vue'
import { api } from '@/common/api.js'
import { cleanNote, formatCompactTime, isDisplayableNote } from '@/common/text.js'

const recent = ref([])
const weekCount = ref(0)
const weeklyGoal = 7
const progressWidth = computed(() => `${Math.min((weekCount.value / weeklyGoal) * 100, 100)}%`)
const progressHint = computed(() => {
  if (weekCount.value >= weeklyGoal) return '本周目标已完成，继续保持'
  return `再解析 ${weeklyGoal - weekCount.value} 条即可完成本周目标`
})

onShow(() => {
  Promise.allSettled([
    api.listNotes({ page: 1, pageSize: 2 }),
    api.dashboard()
  ]).then(([notesResult, dashboardResult]) => {
    recent.value = notesResult.status === 'fulfilled'
      ? (notesResult.value.items || []).filter(isDisplayableNote).map(normalizeNote)
      : []
    weekCount.value = dashboardResult.status === 'fulfilled'
      ? Number(dashboardResult.value?.stats?.weekParsed || 0)
      : 0
  })
})

function normalizeNote(note, index) {
  const item = cleanNote(note)
  const platformType = item.platform === '小红书' ? 'xiaohongshu' : 'douyin'
  return {
    id: item.id,
    title: item.title || '未命名笔记',
    platform: item.platform || '未知平台',
    platformType,
    duration: item.duration || '--:--',
    time: formatCompactTime(item.updated_at || item.created_at),
    tone: index % 2 === 0 ? 'purple' : 'blue'
  }
}

function goImport() {
  uni.reLaunch({ url: '/pages/import/index' })
}

function goLibrary() {
  uni.reLaunch({ url: '/pages/library/index' })
}

function goDetail(id) {
  uni.navigateTo({ url: `/pages/note/detail?id=${id}` })
}

</script>

<style scoped lang="scss">
.home-page {
  background:
    radial-gradient(circle at 24px 110px, rgba(255,120,183,.10), transparent 118px),
    radial-gradient(circle at 92% 42px, rgba(108,76,245,.10), transparent 128px),
    #fff;
}
.hello {
  display: flex;
  align-items: center;
  gap: 9px;
}
.avatar {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: #6c4cf5;
  background: #f1ebff;
}
.hello-text {
  color: #161616;
  font-size: 14px;
  font-weight: 800;
  line-height: 1.35;
}
.hello-sub {
  margin-top: 2px;
  color: #85818d;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.35;
}
.quick-card {
  min-height: 82px;
  margin-top: 18px;
  padding: 14px;
  display: flex;
  align-items: center;
  gap: 12px;
  border-radius: 20px;
  color: #fff;
  background: linear-gradient(135deg, #8c6cff 0%, #c19bff 100%);
  box-shadow: 0 14px 28px rgba(108,76,245,.18);
}
.quick-copy {
  flex: 1;
  min-width: 0;
}
.quick-icon,
.quick-arrow {
  width: 46px;
  height: 46px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 15px;
  background: rgba(255,255,255,.18);
  color: #fff;
}
.quick-title {
  font-size: 17px;
  font-weight: 900;
  line-height: 1.35;
}
.quick-desc {
  margin-top: 3px;
  color: rgba(255,255,255,.8);
  font-size: 11px;
  font-weight: 600;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.quick-arrow {
  flex: 0 0 44px;
  width: 44px;
  height: 44px;
  border-radius: 50%;
}
.progress-card {
  margin-top: 22px;
  padding: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 20px;
  background: #fff;
  box-shadow: 0 10px 24px rgba(15,23,42,.05);
}
.progress-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.progress-name {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #161616;
  font-size: 15px;
  font-weight: 900;
}
.progress-name :deep(.vk-icon) {
  color: #6c4cf5;
}
.progress-count {
  display: flex;
  gap: 4px;
  align-items: center;
}
.progress-count text {
  color: #85818d;
  font-size: 11px;
}
.progress-count strong {
  color: #161616;
  font-size: 20px;
  font-weight: 900;
}
.bar {
  height: 9px;
  margin-top: 14px;
  overflow: hidden;
  border-radius: 999px;
  background: #e5e7eb;
}
.bar-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #ff78b7 0%, #8c6cff 100%);
}
.bar-meta {
  margin-top: 8px;
  color: #85818d;
  font-size: 11px;
  font-weight: 600;
}
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 22px 0 10px;
}
.more-link {
  min-width: 76px;
  min-height: 44px;
  margin: -10px -8px -10px 0;
  padding: 0 8px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 3px;
  color: #475569;
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}
.empty-card {
  min-height: 128px;
  padding: 20px 18px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border: 1px solid #eceaf1;
  border-radius: 20px;
  color: #85818d;
  background: #fafafa;
  font-size: 13px;
  font-weight: 800;
  text-align: center;
}
.empty-action {
  min-width: 88px;
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 19px;
  color: #6c4cf5;
  background: #f1ebff;
  font-size: 13px;
  font-weight: 900;
}
.recent-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.recent-item {
  display: grid;
  grid-template-columns: 106px minmax(0, 1fr) 36px;
  gap: 12px;
  align-items: center;
  min-height: 92px;
  padding: 10px 8px 10px 10px;
}
.recent-info {
  min-width: 0;
}
.recent-title {
  color: #161616;
  font-size: 15px;
  font-weight: 900;
  line-height: 1.35;
}
.recent-meta {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-top: 10px;
  color: #85818d;
  font-size: 12px;
}
.item-arrow {
  width: 36px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #85818d;
}
</style>
