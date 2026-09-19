<template>
  <view class="note-card" :class="note.tone || 'purple'" @tap="$emit('open', note)">
    <view class="note-main">
      <view class="note-title">{{ displayNote.title }}</view>
      <view class="tag">{{ displayNote.tag }}</view>
      <view class="note-summary line-clamp-3">{{ displayNote.summary }}</view>
      <view class="note-time">{{ note.time }}</view>
    </view>
    <view class="fav-btn" :class="{ active: note.favorite }" @tap.stop="$emit('toggleFavorite', note)">
      <VKIcon name="bookmark" :size="20" />
    </view>
  </view>
</template>

<script setup>
import { computed } from 'vue'
import VKIcon from './VKIcon.vue'
import { cleanNote } from '@/common/text.js'

const props = defineProps({ note: { type: Object, required: true } })
defineEmits(['open', 'toggleFavorite'])

const displayNote = computed(() => cleanNote(props.note))
</script>

<style scoped lang="scss">
.note-card {
  position: relative;
  min-height: 150px;
  padding: 16px 56px 16px 16px;
  border: 1px solid #e5e7eb;
  border-radius: 20px;
  background: #ffffff;
  box-shadow: 0 8px 22px rgba(15,23,42,.05);
  box-sizing: border-box;
}
.note-card.purple,
.note-card.yellow,
.note-card.blue,
.note-card.plain { background: #ffffff; }
.note-title {
  color: #161616;
  font-size: 17px;
  font-weight: 900;
  line-height: 1.4;
}
.tag {
  margin-top: 8px;
}
.note-summary {
  margin-top: 9px;
  color: #444;
  font-size: 14px;
  line-height: 1.55;
}
.note-time {
  margin-top: 9px;
  color: #85818d;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.45;
}
.fav-btn {
  position: absolute;
  right: 8px;
  top: 8px;
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  color: #475569;
  background: #f8fafc;
}
.fav-btn.active {
  color: #ff78b7;
  border-color: #ffd0e5;
  background: #fff2f8;
}
.line-clamp-3 {
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}
</style>
