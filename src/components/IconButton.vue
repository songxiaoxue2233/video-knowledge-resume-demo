<template>
  <!-- 统一图标按钮：用文字符号模拟图标，避免三端 SVG 兼容差异。 -->
  <view class="icon-button" @tap="$emit('click')">{{ icon }}</view>
</template>

<script setup>
defineProps({
  icon: {
    type: String,
    default: '·'
  }
})

defineEmits(['click'])
</script>

<style scoped lang="scss">
.icon-button {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #E7EBF0;
  border-radius: 10px;
  color: #1A2333;
  background: #F9FAFB;
  font-size: 16px;
  font-weight: 800;
}
</style>
