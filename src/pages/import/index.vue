<template>
  <view class="phone-page import-page">
    <view class="nav-line">
      <view></view>
      <text class="page-title">视频导入</text>
      <view class="icon-button" @tap="showHelp"><VKIcon name="help" :size="22" /></view>
    </view>

    <view class="import-card">
      <view class="link-bubble"><VKIcon name="link" :size="34" /></view>
      <view class="import-title">粘贴视频链接</view>
      <view class="import-desc">支持抖音、小红书，可一次粘贴多条分享文案或链接</view>

      <view class="input-wrap">
        <textarea
          v-model="linkText"
          auto-height
          maxlength="-1"
          placeholder="粘贴视频链接到这里"
          :style="{ height: `${inputHeight}px` }"
          @linechange="handleInputLineChange"
        />
        <view v-if="linkText" class="clear-btn" @tap="clearInput"><VKIcon name="x" :size="16" /></view>
      </view>

      <view v-if="parsedLinks.length" class="detected">
        <PlatformLogo :type="platformType" />
        <text>已识别 {{ parsedLinks.length }} 条有效链接{{ platform ? ` · ${platform}` : '' }}</text>
      </view>

      <view
        class="primary-button"
        :class="{ disabled: !canParse || parsing }"
        :aria-disabled="!canParse || parsing"
        @tap="startParse"
      >
        {{ parsing ? '后台解析中' : parsedLinks.length > 1 ? `开始解析 ${parsedLinks.length} 条` : '开始解析' }}
      </view>

      <view class="platforms">
        <view class="platform-item"><PlatformLogo type="douyin" /></view>
        <view class="platform-item"><PlatformLogo type="xiaohongshu" /></view>
      </view>
    </view>

    <view v-if="activeTask" class="parse-panel card">
      <view v-for="(step, index) in steps" :key="step.key" class="parse-step" :class="{ active: stepIndex >= index, done: stepIndex > index || activeTask.status === 'success' }">
        <view class="step-dot"><VKIcon v-if="stepIndex > index || activeTask.status === 'success'" name="check" :size="13" /></view>
        <view class="step-text">{{ step.text }}</view>
      </view>
      <view class="parse-progress"><view :style="{ width: progress + '%' }"></view></view>
      <view class="progress-number">{{ progress }}%</view>
      <view class="task-message" :class="{ error: activeTask.status === 'failed' }">{{ activeTask.message }}</view>
      <view v-if="activeTask.status === 'success' && activeTask.noteId" class="primary-button view-note" @tap="goDetail(activeTask.noteId)">查看生成笔记</view>
    </view>

    <view class="section-head">
      <text class="section-title">最近解析记录</text>
      <view class="more-link" @tap="loadHistory">
        {{ refreshing ? '刷新中' : '刷新记录' }} <VKIcon name="clock" :size="16" />
      </view>
    </view>
    <view v-if="records.length === 0" class="empty-card">
      <VKIcon name="link" :size="26" />
      <view class="empty-title">还没有解析记录</view>
      <text>粘贴短视频链接并提交后，可在这里查看实时解析进度。</text>
    </view>
    <view v-else class="record-list">
      <view v-for="item in records" :key="item.taskId" class="record card" @tap="item.noteId && goDetail(item.noteId)">
        <VideoThumb :duration="item.duration || '--:--'" :tone="item.tone" small />
        <view class="record-info">
          <view class="record-title">{{ item.title }}</view>
          <view class="record-meta"><PlatformLogo :type="item.platformType" /><text>{{ item.time }}</text></view>
          <view class="status-pill" :class="{ running: item.status !== 'success', error: item.status === 'failed' }">
            {{ item.statusText }}<text v-if="isRunning(item)"> · {{ item.progress }}%</text>
          </view>
        </view>
        <view v-if="item.noteId" class="record-action"><VKIcon name="chevron" :size="18" /></view>
      </view>
    </view>

    <FloatingTabBar active="import" />
  </view>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { onHide, onShow } from '@dcloudio/uni-app'
import FloatingTabBar from '@/components/FloatingTabBar.vue'
import VideoThumb from '@/components/VideoThumb.vue'
import VKIcon from '@/components/VKIcon.vue'
import PlatformLogo from '@/components/PlatformLogo.vue'
import { api } from '@/common/api.js'
import { formatCompactTime } from '@/common/text.js'

const linkText = ref('')
const inputHeight = ref(52)
const parsing = ref(false)
const activeTask = ref(null)
const records = ref([])
const refreshing = ref(false)
let pollTimer = null
let pollInFlight = false
let pageVisible = false
const taskCacheKey = 'video-knowledge-import-tasks-v1'

const steps = [
  { key: 'link', text: '解析视频链接' },
  { key: 'text', text: '下载、转写与画面识别' },
  { key: 'note', text: 'AI 生成并校验笔记' }
]

function handleInputLineChange(event) {
  const contentHeight = Number(event?.detail?.height) || 28
  inputHeight.value = Math.min(168, Math.max(52, Math.ceil(contentHeight + 24)))
}

function clearInput() {
  linkText.value = ''
  inputHeight.value = 52
}

function detectPlatformType(text = '') {
  const value = String(text || '').toLowerCase()
  if (value.includes('xhs') || value.includes('xiaohongshu') || value.includes('xhslink')) return 'xiaohongshu'
  if (value.includes('douyin') || value.includes('iesdouyin')) return 'douyin'
  return ''
}

function extractLinks(text = '') {
  const matches = text.match(/https?:\/\/[^\s<>'"，。；、]+/g) || []
  return [...new Set(matches.map((item) => item.replace(/[.,;:!?)}\]，。；：！？）】]+$/, '')))].slice(0, 10)
}

const parsedLinks = computed(() => extractLinks(linkText.value))

const platformType = computed(() => {
  const types = [...new Set(parsedLinks.value.map(detectPlatformType).filter(Boolean))]
  return types.length === 1 ? types[0] : ''
})

const platform = computed(() => {
  if (platformType.value === 'xiaohongshu') return '小红书'
  if (platformType.value === 'douyin') return '抖音'
  if (parsedLinks.value.length) return '多平台'
  return ''
})

const canParse = computed(() => parsedLinks.value.length > 0)

const stepIndex = computed(() => {
  const stage = activeTask.value?.stage || activeTask.value?.status || ''
  if (activeTask.value?.status === 'success') return 3
  if (['generating_note', 'validating_note', 'success'].includes(stage)) return 2
  if (['source_ready', 'downloading_video', 'transcribing_audio', 'extracting_visual_text'].includes(stage)) return 1
  return 0
})

const progress = computed(() => Number(activeTask.value?.progress || (activeTask.value?.status === 'success' ? 100 : 5)))

function startParse() {
  if (!canParse.value || parsing.value) return
  parsing.value = true
  clearPoll()
  api.createImportTasks(parsedLinks.value)
    .then((res) => {
      const created = (res.created || []).map((task) => makeRecord({
        ...task,
        title: `${platformName(task.link)}解析任务`,
        platform: platformName(task.link),
        platformType: detectPlatformType(task.link) || 'douyin',
        statusText: '排队中',
        message: '任务已提交，正在后台处理；可以离开当前页面。'
      }))
      records.value = [...created, ...records.value.filter((item) => !created.some((task) => task.taskId === item.taskId))].slice(0, 30)
      activeTask.value = created[0] || null
      persistTaskRecords()
      clearInput()
      uni.showToast({
        title: '已转入后台解析',
        icon: 'success',
        duration: 1800
      })
      startPolling()
    })
    .catch(() => {
      parsing.value = false
    })
}

function startPolling() {
  if (!pageVisible || pollTimer) return
  pollTimer = setInterval(refreshTaskSnapshot, 1800)
}

function refreshTaskSnapshot() {
  if (pollInFlight || !pageVisible) return
  pollInFlight = true
  api.listImportTasks({ page: 1, pageSize: 30 })
    .then((res) => applyTaskSnapshot(res.items || []))
    .finally(() => {
      pollInFlight = false
    })
}

function isRunning(task) {
  return task && ['queued', 'processing'].includes(task.status)
}

function applyTaskSnapshot(tasks) {
  records.value = tasks.map(historyRecord)
  const running = records.value.filter(isRunning)
  parsing.value = running.length > 0
  activeTask.value = running[0] || records.value[0] || null
  persistTaskRecords()
  if (running.length && pageVisible) startPolling()
  else clearPoll()
}

function persistTaskRecords() {
  try {
    uni.setStorageSync(taskCacheKey, JSON.stringify(records.value.slice(0, 30)))
  } catch (_) {}
}

function restoreTaskRecords() {
  try {
    const cached = JSON.parse(uni.getStorageSync(taskCacheKey) || '[]')
    if (!Array.isArray(cached) || !cached.length) return
    records.value = cached.map((item) => makeRecord(item))
    const running = records.value.filter(isRunning)
    parsing.value = running.length > 0
    activeTask.value = running[0] || records.value[0] || null
    if (running.length) startPolling()
  } catch (_) {
    uni.removeStorageSync(taskCacheKey)
  }
}

function makeRecord(extra = {}) {
  return {
    taskId: '',
    title: '视频解析任务',
    status: 'queued',
    stage: 'queued',
    progress: 5,
    message: '',
    noteId: '',
    platform: '未知平台',
    platformType: 'douyin',
    time: formatCompactTime(new Date()),
    tone: extra.platformType === 'xiaohongshu' ? 'purple' : 'blue',
    ...extra
  }
}

function loadHistory(showLoading = true, force = false) {
  if (refreshing.value && !force) return
  refreshing.value = true
  if (showLoading) uni.showNavigationBarLoading()
  api.listImportTasks({ page: 1, pageSize: 30 })
    .then((res) => {
      applyTaskSnapshot(res.items || [])
    })
    .finally(() => {
      refreshing.value = false
      if (showLoading) uni.hideNavigationBarLoading()
    })
}

function historyRecord(task) {
  const type = detectPlatformType(task.link)
  return makeRecord({
    ...task,
    title: task.title || `${platformName(task.link)}解析任务`,
    platform: task.platform || platformName(task.link),
    platformType: type || (task.platform === '小红书' ? 'xiaohongshu' : 'douyin'),
    statusText: statusText(task.status),
    time: formatCompactTime(task.createdAt)
  })
}

function platformName(text = '') {
  const type = detectPlatformType(text)
  return type === 'xiaohongshu' ? '小红书' : type === 'douyin' ? '抖音' : '视频'
}

function statusText(status) {
  if (status === 'success') return '解析完成'
  if (status === 'failed') return '解析失败'
  if (status === 'need_upload') return '需要上传视频'
  if (status === 'queued') return '排队中'
  return '解析中'
}

function clearPoll() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = null
}

function goDetail(id) {
  if (!id) return
  uni.navigateTo({ url: `/pages/note/detail?id=${id}` })
}

function showHelp() {
  uni.showModal({
    title: '如何导入视频',
    content: '复制抖音或小红书分享链接，可一次粘贴最多 10 条。识别成功后点击“开始解析”，任务会在后台继续运行。',
    showCancel: false,
    confirmText: '知道了'
  })
}

function activatePage() {
  if (pageVisible) return
  pageVisible = true
  restoreTaskRecords()
  loadHistory(false, true)
}

// H5 custom navigation does not consistently emit the UniApp onShow hook.
// Vue mounting is the guaranteed fallback when the import route is recreated.
onMounted(activatePage)
onShow(activatePage)
onHide(() => {
  pageVisible = false
  clearPoll()
})
onUnmounted(() => {
  pageVisible = false
  clearPoll()
})
</script>

<style scoped lang="scss">
.import-page {
  background:
    radial-gradient(circle at 88% 70px, rgba(108, 76, 245, 0.10), transparent 120px),
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
.import-card {
  margin-top: 18px;
  padding: 20px 16px;
  border: 1px solid #e6ebf2;
  border-radius: 20px;
  background: linear-gradient(145deg, #f6f9ff 0%, #eef6ff 100%);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.06);
}
.link-bubble {
  width: 58px;
  height: 58px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: #6c4cf5;
  background: #ffffff;
}
.import-title {
  margin-top: 14px;
  color: #161616;
  text-align: center;
  font-size: 22px;
  font-weight: 900;
  line-height: 1.35;
}
.import-desc {
  margin-top: 6px;
  color: #85818d;
  text-align: center;
  font-size: 13px;
  font-weight: 700;
}
.input-wrap {
  position: relative;
  min-height: 52px;
  margin-top: 18px;
  padding: 0 48px 0 16px;
  display: flex;
  align-items: flex-start;
  border: 1px solid #eceaf1;
  border-radius: 26px;
  background: rgba(255, 255, 255, 0.9);
  overflow: hidden;
}
textarea {
  width: 100%;
  min-height: 52px;
  max-height: 168px;
  padding: 14px 0;
  box-sizing: border-box;
  overflow-y: auto;
  color: #161616;
  font-size: 14px;
  line-height: 1.6;
}
.clear-btn {
  position: absolute;
  right: 4px;
  top: 5px;
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: #85818d;
  background: transparent;
}
.detected,
.record-meta {
  display: flex;
  align-items: center;
  gap: 6px;
}
.detected {
  justify-content: center;
  margin-top: 12px;
  color: #6c4cf5;
  font-size: 12px;
  font-weight: 900;
}
.primary-button {
  margin-top: 16px;
}
.platforms {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-top: 14px;
}
.platform-item {
  min-width: 70px;
  min-height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #e6ebf2;
  border-radius: 18px;
  background: rgba(255,255,255,.82);
}
.parse-panel {
  margin-top: 16px;
  padding: 16px;
}
.parse-step {
  min-height: 32px;
  display: flex;
  align-items: center;
  gap: 10px;
  color: #85818d;
  font-size: 14px;
  font-weight: 900;
  line-height: 1.4;
}
.parse-step.active {
  color: #161616;
}
.step-dot {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #eceaf1;
  border-radius: 50%;
  color: #ffffff;
  background: #ffffff;
}
.parse-step.done .step-dot {
  border-color: #6c4cf5;
  background: #6c4cf5;
}
.parse-progress {
  height: 6px;
  margin-top: 12px;
  overflow: hidden;
  border-radius: 999px;
  background: #eceaf1;
}
.parse-progress view {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #8c6cff 0%, #ff78b7 100%);
}
.progress-number {
  margin-top: 6px;
  color: #6c4cf5;
  text-align: right;
  font-size: 12px;
  font-weight: 900;
}
.task-message {
  margin-top: 10px;
  color: #85818d;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.5;
}
.task-message.error {
  color: #ff4d4f;
}
.view-note {
  margin-top: 16px;
}
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 22px 0 10px;
}
.more-link {
  min-width: 84px;
  min-height: 44px;
  margin: -10px -8px -10px 0;
  padding: 0 8px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  color: #475569;
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}
.empty-card {
  min-height: 148px;
  padding: 24px 22px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border-radius: 20px;
  color: #85818d;
  border: 1px dashed #dbe2ea;
  background: #fafafa;
  text-align: center;
  font-size: 13px;
  font-weight: 800;
  line-height: 1.5;
}
.empty-title {
  color: #161616;
  font-size: 15px;
  font-weight: 900;
}
.record-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.record {
  display: grid;
  grid-template-columns: 106px minmax(0, 1fr) 36px;
  gap: 12px;
  align-items: center;
  padding: 10px;
}
.record-info {
  min-width: 0;
}
.record-title {
  color: #161616;
  font-size: 17px;
  font-weight: 900;
  line-height: 1.4;
}
.record-meta {
  margin-top: 6px;
  color: #85818d;
  font-size: 12px;
  font-weight: 700;
}
.record-action {
  width: 36px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #85818d;
}
.status-pill {
  width: fit-content;
  margin-top: 8px;
  padding: 4px 9px;
  border-radius: 999px;
  color: #1d925a;
  background: rgba(56, 161, 105, 0.14);
  font-size: 12px;
  font-weight: 900;
}
.status-pill.running {
  color: #6c4cf5;
  background: rgba(108, 76, 245, 0.12);
}
.status-pill.error {
  color: #ff4d4f;
  background: #fff2f0;
}
</style>
