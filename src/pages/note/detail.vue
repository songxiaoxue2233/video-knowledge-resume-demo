<template>
  <view class="phone-page detail-page">
    <view class="detail-nav">
      <view class="icon-button" @tap="back"><VKIcon name="back" :size="21" /></view>
      <text>笔记详情</text>
      <view class="nav-actions">
        <view class="icon-button favorite" :class="{ active: favorite }" @tap="toggleFavorite"><VKIcon name="bookmark" :size="20" /></view>
        <view class="icon-button" @tap="runDetailAction('markdown')"><VKIcon name="more" :size="20" /></view>
      </view>
    </view>

    <view v-if="loading" class="empty-card">
      <VKIcon name="book" :size="28" />
      <text>正在加载笔记...</text>
    </view>
    <view v-else-if="!note.id" class="empty-card">
      <VKIcon name="book" :size="28" />
      <text>未找到这条笔记</text>
    </view>

    <template v-else>
      <view class="video-card card">
        <VideoThumb :duration="note.duration || '--:--'" :tone="note.tone" />
        <view class="video-info">
          <view class="video-title">{{ note.title }}</view>
          <view class="video-meta"><PlatformLogo :type="note.platformType" />{{ note.platform }} · {{ note.duration || '--:--' }}</view>
          <view class="link-row" @tap="toast('原视频链接打开能力已预留')">
            <VKIcon name="link" :size="15" />
            <text>{{ note.source_url || '暂无原视频链接' }}</text>
          </view>
        </view>
      </view>

      <view class="summary-card">
        <view class="summary-label">一句话摘要</view>
        <view class="summary-text">{{ note.summary || '暂无摘要' }}</view>
      </view>

      <view class="module-card card">
        <view class="module-head" @tap="toggle('core')">
          <view>
            <view class="module-title">核心知识点拆解</view>
            <view class="module-sub">{{ knowledgeMeta }}</view>
          </view>
          <VKIcon name="chevron" :size="18" :class="{ open: expanded.core }" />
        </view>
        <view v-if="expanded.core" class="module-body">
          <view class="knowledge-list">
            <view
              v-for="(block, index) in visibleKnowledgeBlocks"
              :key="`${block.type}-${index}`"
              class="knowledge-block"
              :class="[`knowledge-${block.type}`, `level-${block.level || 0}`]"
            >
              <template v-if="block.type === 'section'">
                <view class="section-index">{{ block.sectionIndex }}</view>
                <view class="knowledge-section-title">{{ block.text }}</view>
              </template>
              <template v-else-if="block.type === 'subsection'">
                <view class="subsection-line"></view>
                <view class="knowledge-subsection-title">{{ block.text }}</view>
              </template>
              <template v-else-if="block.type === 'ordered' || block.type === 'bullet'">
                <view class="knowledge-marker">{{ block.type === 'ordered' ? block.marker : '•' }}</view>
                <view class="knowledge-content">
                  <view v-if="block.title" class="knowledge-item-title">{{ block.title }}</view>
                  <view v-if="block.body" class="knowledge-item-body">{{ block.body }}</view>
                </view>
              </template>
              <view v-else class="knowledge-paragraph">{{ block.text }}</view>
            </view>
          </view>
          <view
            v-if="knowledgeBlocks.length > previewBlockCount"
            class="knowledge-toggle"
            @tap="showAllKnowledge = !showAllKnowledge"
          >
            {{ showAllKnowledge ? '收起内容' : `展开全部 ${knowledgeBlocks.length} 个知识块` }}
            <VKIcon name="chevron" :size="16" :class="{ open: showAllKnowledge }" />
          </view>
        </view>
      </view>

      <view class="module-card card">
        <view class="module-head" @tap="toggle('annotation')">
          <view>
            <view class="module-title">个人学习批注</view>
            <view class="module-sub">由用户自己沉淀</view>
          </view>
          <VKIcon name="chevron" :size="18" :class="{ open: expanded.annotation }" />
        </view>
        <view v-if="expanded.annotation" class="module-body">
          <textarea v-model="annotation" placeholder="写下你的重点、疑问、迁移场景或复盘行动..." />
        </view>
      </view>

      <view class="bottom-actions">
        <view class="action-btn" :class="{ disabled: exporting }" @tap="runDetailAction('feishu')">同步飞书</view>
        <view class="action-btn" :class="{ disabled: exporting }" @tap="runDetailAction('word')">导出Word</view>
      </view>
    </template>
  </view>
</template>

<script setup>
import { onLoad } from '@dcloudio/uni-app'
import { computed, ref } from 'vue'
import VKIcon from '@/components/VKIcon.vue'
import VideoThumb from '@/components/VideoThumb.vue'
import PlatformLogo from '@/components/PlatformLogo.vue'
import { api } from '@/common/api.js'
import { cleanNote } from '@/common/text.js'
import { exportMarkdown, exportWord, syncFeishu } from '@/common/actions.js'

const note = ref({})
const loading = ref(false)
const exporting = ref(false)
const favorite = ref(false)
const annotation = ref('')
const expanded = ref({ core: true, annotation: true })
const showAllKnowledge = ref(false)
const previewBlockCount = 18

const knowledgeBlocks = computed(() => parseKnowledgeMarkdown(note.value.theory))
const visibleKnowledgeBlocks = computed(() => {
  if (showAllKnowledge.value || knowledgeBlocks.value.length <= previewBlockCount) return knowledgeBlocks.value
  return knowledgeBlocks.value.slice(0, previewBlockCount)
})
const knowledgeMeta = computed(() => {
  const sections = knowledgeBlocks.value.filter((block) => block.type === 'section').length
  const points = knowledgeBlocks.value.filter((block) => ['ordered', 'bullet'].includes(block.type)).length
  const structure = !sections && !points ? 'AI 结构化整理' : `${sections} 个主题 · ${points} 个要点`
  const category = String(note.value.category || '').trim()
  return category && category !== '待分类' ? `${category} · ${structure}` : structure
})

onLoad((query) => {
  if (!query?.id) return
  loading.value = true
  api.getNote(query.id)
    .then((res) => {
      note.value = normalizeNote(res)
    })
    .catch(() => {
      note.value = {}
    })
    .finally(() => {
      loading.value = false
    })
})

function normalizeNote(data) {
  const item = cleanNote(data)
  const platformType = item.platform === '小红书' ? 'xiaohongshu' : 'douyin'
  return { ...item, platformType, tone: platformType === 'xiaohongshu' ? 'purple' : 'blue' }
}

function stripInlineMarkdown(value = '') {
  return String(value)
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/__(.*?)__/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/[*_~]/g, '')
    .trim()
}

function splitKnowledgeContent(value = '') {
  const boldTitle = String(value).match(/^\*\*(.+?)\*\*\s*[：:]\s*(.*)$/)
  if (boldTitle) {
    return {
      title: stripInlineMarkdown(boldTitle[1]),
      body: stripInlineMarkdown(boldTitle[2])
    }
  }
  const clean = stripInlineMarkdown(value)
  const separator = clean.match(/^(.{2,24})[：:]\s*(.+)$/)
  if (separator) return { title: separator[1].trim(), body: separator[2].trim() }
  return { title: '', body: clean }
}

function parseKnowledgeMarkdown(value = '') {
  const source = String(value || '').replace(/\r\n?/g, '\n').trim()
  if (!source) return [{ type: 'paragraph', text: '后台还没有返回完整结构化笔记。', level: 0 }]

  let sectionIndex = 0
  const blocks = []
  source.split('\n').forEach((rawLine) => {
    if (!rawLine.trim()) return
    const indent = (rawLine.match(/^\s*/) || [''])[0].replace(/\t/g, '  ').length
    const level = Math.min(Math.floor(indent / 2), 2)
    const line = rawLine.trim()
    const section = line.match(/^##\s+(.+)$/)
    if (section) {
      sectionIndex += 1
      blocks.push({
        type: 'section',
        text: stripInlineMarkdown(section[1]),
        sectionIndex: String(sectionIndex).padStart(2, '0'),
        level: 0
      })
      return
    }
    const subsection = line.match(/^###\s+(.+)$/)
    if (subsection) {
      blocks.push({ type: 'subsection', text: stripInlineMarkdown(subsection[1]), level: 0 })
      return
    }
    const ordered = line.match(/^(\d+)[.、]\s*(.+)$/)
    if (ordered) {
      blocks.push({
        type: 'ordered',
        marker: ordered[1],
        ...splitKnowledgeContent(ordered[2]),
        level
      })
      return
    }
    const bullet = line.match(/^[-•]\s+(.+)$/)
    if (bullet) {
      blocks.push({ type: 'bullet', marker: '•', ...splitKnowledgeContent(bullet[1]), level })
      return
    }
    blocks.push({ type: 'paragraph', text: stripInlineMarkdown(line), level })
  })
  return blocks
}

function toggle(key) {
  expanded.value[key] = !expanded.value[key]
}

function toggleFavorite() {
  favorite.value = !favorite.value
  uni.showToast({ title: favorite.value ? '已收藏' : '已取消收藏', icon: 'none' })
}

function back() {
  const pages = getCurrentPages()
  if (pages.length > 1) uni.navigateBack()
  else uni.reLaunch({ url: '/pages/library/index' })
}

function toast(title) {
  uni.showToast({ title, icon: 'none' })
}

function runDetailAction(type) {
  if (exporting.value || !note.value.id) return
  const ids = [note.value.id]
  const actions = {
    feishu: () => syncFeishu(ids),
    word: () => exportWord(ids),
    markdown: () => exportMarkdown(ids)
  }
  const titles = { feishu: '同步飞书', word: '导出Word', markdown: '导出Markdown' }
  exporting.value = true
  uni.showLoading({ title: titles[type] || '正在导出' })
  actions[type]()
    .finally(() => {
      exporting.value = false
      uni.hideLoading()
    })
}
</script>

<style scoped lang="scss">
.detail-page {
  padding-bottom: calc(92px + env(safe-area-inset-bottom));
  background:
    radial-gradient(circle at 88% 80px, rgba(108, 76, 245, 0.10), transparent 120px),
    #fff;
}
.detail-nav {
  display: grid;
  grid-template-columns: 44px 1fr 98px;
  align-items: center;
  gap: 8px;
}
.detail-nav > text {
  color: #161616;
  text-align: center;
  font-size: 17px;
  font-weight: 900;
  line-height: 1.4;
}
.nav-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.favorite.active {
  color: #ff78b7;
}
.empty-card {
  min-height: 160px;
  margin-top: 22px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border-radius: 20px;
  color: #85818d;
  background: #f8f7fc;
  font-size: 14px;
  font-weight: 900;
  line-height: 1.65;
}
.video-card {
  display: flex;
  gap: 14px;
  margin-top: 22px;
  padding: 12px;
}
.video-info {
  min-width: 0;
  flex: 1;
}
.video-title {
  color: #161616;
  font-size: 17px;
  font-weight: 900;
  line-height: 1.4;
}
.video-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  color: #85818d;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.45;
}
.link-row {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 10px;
  color: #6c4cf5;
  font-size: 12px;
  font-weight: 900;
}
.link-row text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.summary-card {
  margin-top: 12px;
  padding: 18px;
  border-radius: 20px;
  background: linear-gradient(135deg, #f0ebff 0%, #fff1f8 100%);
}
.summary-label {
  color: #6c4cf5;
  font-size: 12px;
  font-weight: 900;
}
.summary-text {
  margin-top: 9px;
  color: #161616;
  font-size: 17px;
  font-weight: 900;
  line-height: 1.65;
}
.module-card {
  margin-top: 12px;
  padding: 18px;
}
.module-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.module-title {
  color: #161616;
  font-size: 20px;
  font-weight: 900;
  line-height: 1.35;
}
.module-sub {
  width: fit-content;
  margin-top: 7px;
  padding: 4px 10px;
  border-radius: 999px;
  color: #6c4cf5;
  background: rgba(108, 76, 245, 0.10);
  font-size: 12px;
  font-weight: 900;
}
.module-head :deep(.vk-icon) {
  transition: transform 0.2s;
}
.module-head :deep(.open) {
  transform: rotate(90deg);
}
.module-body {
  margin-top: 16px;
}
.knowledge-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.knowledge-block {
  box-sizing: border-box;
}
.knowledge-section {
  margin-top: 8px;
  padding: 14px;
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  border-radius: 16px;
  background: linear-gradient(135deg, #f0ebff 0%, #fff4fa 100%);
}
.knowledge-section:first-child {
  margin-top: 0;
}
.section-index {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  color: #ffffff;
  background: #6c4cf5;
  font-size: 12px;
  font-weight: 900;
}
.knowledge-section-title {
  color: #21075f;
  font-size: 16px;
  font-weight: 900;
  line-height: 1.45;
}
.knowledge-subsection {
  margin-top: 8px;
  padding: 8px 2px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.subsection-line {
  width: 4px;
  height: 20px;
  margin-top: 2px;
  flex: 0 0 4px;
  border-radius: 2px;
  background: #ff78b7;
}
.knowledge-subsection-title {
  color: #161616;
  font-size: 15px;
  font-weight: 900;
  line-height: 1.5;
}
.knowledge-ordered,
.knowledge-bullet {
  padding: 11px 12px;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  border: 1px solid #eceaf1;
  border-radius: 14px;
  background: #ffffff;
}
.knowledge-bullet {
  border-color: transparent;
  background: #f8f7fc;
}
.knowledge-block.level-1 {
  margin-left: 12px;
}
.knowledge-block.level-2 {
  margin-left: 24px;
}
.knowledge-marker {
  width: 24px;
  height: 24px;
  flex: 0 0 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: #6c4cf5;
  background: rgba(108, 76, 245, 0.10);
  font-size: 12px;
  font-weight: 900;
}
.knowledge-content {
  min-width: 0;
  flex: 1;
}
.knowledge-item-title {
  color: #161616;
  font-size: 14px;
  font-weight: 900;
  line-height: 1.5;
}
.knowledge-item-body {
  margin-top: 3px;
  color: #55515d;
  font-size: 13px;
  line-height: 1.65;
}
.knowledge-paragraph {
  padding: 4px 2px;
  color: #55515d;
  font-size: 13px;
  line-height: 1.7;
}
.knowledge-toggle {
  min-height: 44px;
  margin-top: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  border-radius: 14px;
  color: #6c4cf5;
  background: #f1ebff;
  font-size: 13px;
  font-weight: 900;
}
.knowledge-toggle :deep(.vk-icon) {
  transition: transform .2s;
}
.knowledge-toggle :deep(.open) {
  transform: rotate(90deg);
}
textarea {
  width: 100%;
  min-height: 128px;
  padding: 14px;
  border-radius: 16px;
  color: #161616;
  background: #f8f7fc;
  font-size: 14px;
  line-height: 1.65;
}
.bottom-actions {
  position: fixed;
  left: 16px;
  right: 16px;
  bottom: calc(10px + env(safe-area-inset-bottom));
  max-width: 398px;
  height: 64px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  padding: 8px;
  border-radius: 32px;
  background: #21075f;
  box-shadow: 0 18px 34px rgba(33, 7, 95, 0.28);
}
.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 24px;
  color: #21075f;
  background: #fff;
  font-size: 13px;
  font-weight: 900;
  line-height: 1;
}
.action-btn.disabled {
  opacity: 0.45;
}
</style>
