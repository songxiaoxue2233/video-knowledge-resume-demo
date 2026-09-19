<template>
  <view class="empty-state">
    <view class="empty-icon">{{ iconMap[type] || '□' }}</view>
    <view class="empty-title">{{ title || defaultTitle }}</view>
    <view class="empty-desc">{{ desc || defaultDesc }}</view>
    <view v-if="buttonText" class="primary-btn empty-btn" @tap="$emit('action')">{{ buttonText }}</view>
  </view>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  type: { type: String, default: 'empty' },
  title: { type: String, default: '' },
  desc: { type: String, default: '' },
  buttonText: { type: String, default: '' }
})
defineEmits(['action'])

const iconMap = { empty: '空', notes: '文', history: '历', quota: '额', network: '网' }
const titleMap = {
  notes: '暂无笔记',
  history: '暂无导入历史',
  quota: '解析额度已用完',
  network: '网络连接异常'
}
const descMap = {
  notes: '导入视频链接后，AI生成的结构化笔记会出现在这里。',
  history: '批量导入后可在这里查看历史记录。',
  quota: '升级会员后可继续解析更多视频。',
  network: '请检查本地后端或网络连接。'
}
const defaultTitle = computed(() => titleMap[props.type] || '暂无数据')
const defaultDesc = computed(() => descMap[props.type] || '当前没有可展示内容。')
</script>

<style scoped lang="scss">
.empty-state {
  padding: 28px 18px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  color: #888888;
}
.empty-icon {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 18px;
  color: #38A169;
  background: #EAF7F1;
  font-weight: 900;
}
.empty-title {
  margin-top: 12px;
  color: #222222;
  font-size: 15px;
  font-weight: 900;
}
.empty-desc {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.6;
}
.empty-btn {
  margin-top: 14px;
}
</style>
