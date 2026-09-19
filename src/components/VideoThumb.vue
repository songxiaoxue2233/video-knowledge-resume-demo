<template>
  <view class="video-thumb" :class="[tone, { small }]">
    <view class="play-wrap"><VKIcon name="play" :size="small ? 16 : 20" /></view>
    <text v-if="duration && duration !== '--:--'" class="duration">{{ duration }}</text>
  </view>
</template>

<script setup>
import VKIcon from './VKIcon.vue'

defineProps({
  duration: { type: String, default: '' },
  tone: { type: String, default: 'purple' },
  small: { type: Boolean, default: false }
})
</script>

<style scoped lang="scss">
.video-thumb {
  position: relative;
  width: 124px;
  height: 76px;
  flex-shrink: 0;
  overflow: hidden;
  border-radius: 14px;
  background: linear-gradient(135deg, #ede7ff 0%, #dff4ff 100%);
}
.video-thumb.small {
  width: 106px;
  height: 68px;
}
.video-thumb.yellow {
  background: linear-gradient(135deg, #fff1b8 0%, #ffe2a8 100%);
}
.video-thumb.blue {
  background: linear-gradient(135deg, #d9f3ff 0%, #e7e2ff 100%);
}
.play-wrap {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: rgba(33, 7, 95, .35);
  background: rgba(255,255,255,.5);
  transform: translate(-50%, -50%);
}
.duration {
  position: absolute;
  right: 8px;
  bottom: 7px;
  padding: 3px 6px;
  border-radius: 8px;
  color: #fff;
  background: rgba(22,22,22,.62);
  font-size: 11px;
  font-weight: 800;
}
</style>
