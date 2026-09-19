<template>
  <view class="platform-logo" :class="type">
    <text>{{ type === 'xiaohongshu' ? '小红书' : '抖音' }}</text>
  </view>
</template>

<script setup>
defineProps({ type: { type: String, default: 'douyin' } })
</script>

<style scoped lang="scss">
.platform-logo {
  height: 22px;
  min-width: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  padding: 0 7px;
  border-radius: 999px;
}
.platform-logo text {
  color: #ffffff;
  font-size: 10px;
  font-weight: 900;
  line-height: 1;
}
.platform-logo.douyin {
  background: #000000;
}
.platform-logo.xiaohongshu {
  background: #ff2442;
}
</style>
