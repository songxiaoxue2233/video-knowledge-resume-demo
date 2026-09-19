<template>
  <!-- 详情页底部固定操作栏：飞书云同步 + Word 本地导出。 -->
  <view class="sync-action-bar">
    <view class="primary-btn action-btn" @tap="syncFeishu">同步飞书</view>
    <view class="primary-btn action-btn" @tap="exportWord">导出Word</view>
  </view>
</template>

<script setup>
import { syncFeishu, exportWord } from '@/common/actions.js'
</script>

<style scoped lang="scss">
.sync-action-bar {
  position: fixed;
  left: 12px;
  right: 12px;
  bottom: calc(14px + env(safe-area-inset-bottom));
  z-index: 80;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  padding: 10px;
  border: 1px solid #E7EBF0;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 12px 30px rgba(26, 35, 51, 0.16);
  box-sizing: border-box;
}

.action-btn {
  min-width: 0;
  padding: 0 8px;
  font-size: 12px;
}
</style>
