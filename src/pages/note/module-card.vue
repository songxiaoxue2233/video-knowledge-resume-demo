<template>
  <view class="card section-card">
    <view class="section-head">
      <view><text class="section-title">{{ title }}</text><view class="ai-badge">{{ badge }}</view></view>
      <text class="text-link" @tap="$emit('edit')">编辑</text>
    </view>
    <slot />
  </view>
</template>

<script setup>
defineProps({ title:String, badge:String })
defineEmits(['edit'])
</script>

<style scoped lang="scss">
.ai-badge{align-self:flex-start;height:22px;margin-top:6px;padding:0 8px;display:flex;align-items:center;border-radius:999px;color:#137B52;background:#EAF7F1;font-size:11px;font-weight:800}
</style>
