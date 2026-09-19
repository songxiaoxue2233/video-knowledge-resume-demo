<template>
  <view class="floating-tab">
    <view
      v-for="item in items"
      :key="item.key"
      class="tab-item"
      :class="{ active: active === item.key }"
      @tap="go(item)"
    >
      <VKIcon :name="item.icon" :size="22" />
      <text>{{ item.text }}</text>
    </view>
  </view>
</template>

<script setup>
import VKIcon from './VKIcon.vue'

const props = defineProps({ active: { type: String, default: 'home' } })

const items = [
  { key: 'home', text: '首页', icon: 'home', url: '/pages/dashboard/index' },
  { key: 'import', text: '导入', icon: 'link', url: '/pages/import/index' },
  { key: 'library', text: '知识库', icon: 'book', url: '/pages/library/index' },
  { key: 'mine', text: '我的', icon: 'user', url: '/pages/mine/mine' }
]

function go(item) {
  if (item.key === props.active) return
  uni.reLaunch({ url: item.url })
}
</script>

<style scoped lang="scss">
.floating-tab {
  position: fixed;
  left: 16px;
  right: 16px;
  bottom: calc(10px + env(safe-area-inset-bottom));
  z-index: 100;
  max-width: 398px;
  height: 68px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  align-items: center;
  padding: 8px;
  border-radius: 34px;
  background: #21075f;
  box-shadow: 0 18px 34px rgba(33, 7, 95, 0.28);
  box-sizing: border-box;
}
.tab-item {
  min-width: 0;
  height: 52px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  border-radius: 26px;
  color: rgba(255, 255, 255, 0.82);
  font-size: 11px;
  font-weight: 700;
}
.tab-item.active {
  flex-direction: row;
  gap: 6px;
  color: #21075f;
  background: #ffffff;
}
.tab-item.active text {
  font-weight: 900;
}
</style>
