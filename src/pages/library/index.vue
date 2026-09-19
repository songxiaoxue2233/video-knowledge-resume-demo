<template>
  <view class="phone-page library-page">
    <view class="top-row">
      <text class="page-title">我的知识库</text>
      <view class="actions">
        <view class="action-button" :class="{ active: showFilter }" @tap="showFilter = !showFilter">
          <VKIcon name="filter" :size="19" /><text>筛选</text>
        </view>
        <view class="action-button" @tap="openExport">
          <VKIcon name="arrow" :size="19" /><text>导出</text>
        </view>
      </view>
    </view>

    <view class="search-box">
      <VKIcon name="search" :size="18" />
      <input v-model="keyword" placeholder="搜索笔记、标签或内容" confirm-type="search" />
      <view v-if="keyword" class="search-clear" @tap="keyword = ''"><VKIcon name="x" :size="16" /></view>
    </view>

    <view v-if="showFilter" class="filter-panel card">
      <view
        v-for="option in sortOptions"
        :key="option.key"
        class="filter-chip"
        :class="{ active: sortMode === option.key }"
        @tap="sortMode = option.key"
      >{{ option.text }}</view>
    </view>

    <scroll-view class="tag-scroller" scroll-x :show-scrollbar="false">
      <view class="tag-list">
        <view class="tag-chip" :class="{ active: selectedTag === '' }" @tap="selectedTag = ''">全部</view>
        <view
          v-for="tag in quickTags"
          :key="tag"
          class="tag-chip"
          :class="{ active: selectedTag === tag }"
          @tap="selectedTag = tag"
        >{{ tag }}</view>
      </view>
    </scroll-view>

    <view class="section-head">
      <text class="section-title">{{ selectedTag ? selectedTag : '所有笔记' }}</text>
      <text class="result-count">{{ filteredNotes.length }} 条</text>
    </view>

    <view v-if="filteredNotes.length === 0" class="state-card">
      <VKIcon name="book" :size="26" />
      <text>暂无笔记。解析完成的视频会自动进入知识库。</text>
    </view>
    <view v-else class="note-list">
      <NoteCard
        v-for="note in filteredNotes"
        :key="note.id"
        :note="note"
        @open="openNote"
        @toggleFavorite="toggleFavorite"
      />
    </view>

    <view v-if="showExport" class="export-mask" @tap="showExport = false"></view>
    <view v-if="showExport" class="export-sheet">
      <view class="sheet-handle"></view>
      <view class="sheet-title">导出知识库</view>
      <view class="sheet-desc">当前列表 {{ filteredNotes.length }} 条，可导出 Markdown 或 Word 文件。</view>
      <view class="export-grid">
        <view class="export-btn primary" :class="{ disabled: exporting }" @tap="runExport('word-current')">
          <VKIcon name="book" :size="18" />
          <text>当前列表 Word</text>
        </view>
        <view class="export-btn" :class="{ disabled: exporting }" @tap="runExport('markdown-current')">
          <VKIcon name="book" :size="18" />
          <text>当前列表 Markdown</text>
        </view>
        <view class="export-btn" :class="{ disabled: exporting }" @tap="runExport('word-all')">
          <VKIcon name="book" :size="18" />
          <text>全部 Word</text>
        </view>
        <view class="export-btn" :class="{ disabled: exporting }" @tap="runExport('markdown-all')">
          <VKIcon name="book" :size="18" />
          <text>全部 Markdown</text>
        </view>
      </view>
      <view class="third-row">
        <view class="third-btn" :class="{ disabled: exporting }" @tap="runExport('feishu-current')">同步飞书</view>
      </view>
    </view>

    <FloatingTabBar active="library" />
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import FloatingTabBar from '@/components/FloatingTabBar.vue'
import NoteCard from '@/components/NoteCard.vue'
import VKIcon from '@/components/VKIcon.vue'
import { api } from '@/common/api.js'
import { cleanNote, formatCompactTime, isDisplayableNote } from '@/common/text.js'
import { exportMarkdown, exportWord, syncFeishu } from '@/common/actions.js'

const keyword = ref('')
const showFilter = ref(false)
const showExport = ref(false)
const exporting = ref(false)
const notes = ref([])
const selectedTag = ref('')
const sortMode = ref('latest')
const favoriteIds = ref(new Set())
const FAVORITES_KEY = 'video-knowledge-favorite-note-ids'
const sortOptions = [
  { key: 'latest', text: '最近更新' },
  { key: 'oldest', text: '最早更新' },
  { key: 'favorites', text: '仅看收藏' }
]

onShow(() => {
  favoriteIds.value = new Set(uni.getStorageSync(FAVORITES_KEY) || [])
  loadNotes()
})

function loadNotes() {
  api.listNotes({ page: 1, pageSize: 50, keyword: keyword.value })
    .then((res) => {
      notes.value = (res.items || []).filter(isDisplayableNote).map(normalizeNote)
    })
    .catch(() => {
      notes.value = []
    })
}

function normalizeNote(note, index) {
  const item = cleanNote(note)
  return {
    ...item,
    time: formatCompactTime(item.updated_at || item.created_at),
    tone: 'plain',
    favorite: favoriteIds.value.has(item.id)
  }
}

const quickTags = computed(() => {
  const values = []
  notes.value.forEach((note) => {
    const tags = Array.isArray(note.tags) ? note.tags : [note.tag]
    tags.filter(Boolean).forEach((tag) => {
      if (!values.includes(tag)) values.push(tag)
    })
  })
  return values.slice(0, 10)
})

const filteredNotes = computed(() => {
  const key = keyword.value.trim().toLowerCase()
  const result = notes.value.filter((note) => {
    const tags = Array.isArray(note.tags) ? note.tags : [note.tag]
    const matchesKeyword = !key || [note.title, ...tags, note.summary].join(' ').toLowerCase().includes(key)
    const matchesTag = !selectedTag.value || tags.includes(selectedTag.value)
    const matchesFavorite = sortMode.value !== 'favorites' || note.favorite
    return matchesKeyword && matchesTag && matchesFavorite
  })
  if (sortMode.value === 'oldest') return [...result].reverse()
  return result
})

function toggleFavorite(note) {
  note.favorite = !note.favorite
  const ids = new Set(favoriteIds.value)
  if (note.favorite) ids.add(note.id)
  else ids.delete(note.id)
  favoriteIds.value = ids
  uni.setStorageSync(FAVORITES_KEY, [...ids])
  uni.showToast({ title: note.favorite ? '已收藏' : '已取消收藏', icon: 'none' })
}

function openNote(note) {
  uni.navigateTo({ url: `/pages/note/detail?id=${note.id}` })
}

function openExport() {
  if (notes.value.length === 0) {
    uni.showToast({ title: '暂无可导出的笔记', icon: 'none' })
    return
  }
  showExport.value = true
}

function currentIds() {
  return filteredNotes.value.map((note) => note.id).filter(Boolean)
}

function runExport(type) {
  if (exporting.value) return
  const ids = type.endsWith('all') ? [] : currentIds()
  if (!type.endsWith('all') && ids.length === 0) {
    uni.showToast({ title: '当前列表暂无可导出的笔记', icon: 'none' })
    return
  }
  const actions = {
    'word-current': () => exportWord(ids),
    'markdown-current': () => exportMarkdown(ids),
    'word-all': () => exportWord([]),
    'markdown-all': () => exportMarkdown([]),
    'feishu-current': () => syncFeishu(ids)
  }
  exporting.value = true
  uni.showLoading({ title: '正在生成文件' })
  actions[type]()
    .then(() => {
      showExport.value = false
    })
    .finally(() => {
      exporting.value = false
      uni.hideLoading()
    })
}
</script>

<style scoped lang="scss">
.library-page {
  background:
    radial-gradient(circle at 88% 82px, rgba(255,120,183,.10), transparent 116px),
    #fff;
}
.actions {
  display: flex;
  gap: 8px;
}
.action-button {
  min-width: 54px;
  height: 44px;
  padding: 0 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  color: #475569;
  background: #ffffff;
  font-size: 11px;
  font-weight: 800;
  white-space: nowrap;
}
.action-button.active {
  color: #6c4cf5;
  border-color: #d7ccff;
  background: #f1ebff;
}
.search-box {
  height: 48px;
  margin-top: 16px;
  padding: 0 6px 0 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid #eceaf1;
  border-radius: 16px;
  color: #85818d;
  background: #fff;
  box-sizing: border-box;
}
.search-box input {
  flex: 1;
  color: #161616;
  font-size: 14px;
}
.search-clear {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #85818d;
}
.filter-panel {
  flex-wrap: wrap;
  display: flex;
  gap: 8px;
  margin-top: 12px;
  padding: 12px;
}
.filter-chip {
  min-height: 38px;
  padding: 0 12px;
  display: flex;
  align-items: center;
  border-radius: 999px;
  color: #85818d;
  background: #f8f7fc;
  font-size: 12px;
  font-weight: 900;
}
.filter-chip.active {
  color: #fff;
  background: #6c4cf5;
}
.tag-scroller {
  width: 100%;
  margin-top: 14px;
  white-space: nowrap;
}
.tag-list {
  display: inline-flex;
  gap: 8px;
  padding-right: 20px;
}
.tag-chip {
  min-width: 54px;
  height: 36px;
  padding: 0 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #e5e7eb;
  border-radius: 18px;
  color: #64748b;
  background: #ffffff;
  font-size: 12px;
  font-weight: 800;
  white-space: nowrap;
}
.tag-chip.active {
  color: #6c4cf5;
  border-color: #d7ccff;
  background: #f1ebff;
}
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 20px 0 10px;
}
.result-count {
  color: #85818d;
  font-size: 12px;
  font-weight: 700;
}
.note-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.state-card {
  min-height: 138px;
  padding: 28px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border-radius: 20px;
  color: #85818d;
  background: #f8f7fc;
  text-align: center;
  font-size: 14px;
  font-weight: 800;
}
.export-mask {
  position: fixed;
  left: 0;
  right: 0;
  top: 0;
  bottom: 0;
  z-index: 150;
  background: rgba(22, 22, 22, 0.22);
}
.export-sheet {
  position: fixed;
  left: 16px;
  right: 16px;
  bottom: calc(92px + env(safe-area-inset-bottom));
  z-index: 151;
  max-width: 398px;
  margin: 0 auto;
  padding: 10px 14px 16px;
  border: 1px solid #eceaf1;
  border-radius: 20px;
  background: #ffffff;
  box-shadow: 0 24px 50px rgba(33, 7, 95, 0.22);
}
.sheet-handle {
  width: 38px;
  height: 4px;
  margin: 0 auto 14px;
  border-radius: 999px;
  background: #eceaf1;
}
.sheet-title {
  color: #161616;
  font-size: 20px;
  font-weight: 900;
  line-height: 1.35;
}
.sheet-desc {
  margin-top: 5px;
  color: #85818d;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.45;
}
.export-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
  margin-top: 14px;
}
.export-btn {
  min-height: 72px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  border-radius: 16px;
  color: #6c4cf5;
  background: #f8f7fc;
  font-size: 13px;
  font-weight: 900;
}
.export-btn.primary {
  color: #ffffff;
  background: linear-gradient(100deg, #8c6cff 0%, #ff78b7 100%);
}
.third-row {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
  margin-top: 10px;
}
.third-btn {
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #eceaf1;
  border-radius: 22px;
  color: #21075f;
  background: #ffffff;
  font-size: 13px;
  font-weight: 900;
}
.disabled {
  opacity: 0.45;
}
</style>
