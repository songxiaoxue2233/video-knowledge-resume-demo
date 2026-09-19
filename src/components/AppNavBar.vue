<template>
  <!-- 自定义顶部导航：替代系统导航，保证三端视觉一致。 -->
  <view class="app-navbar">
    <view class="nav-left">
      <slot name="left">
        <view v-if="showBrand" class="brand">
          <view class="logo">书</view>
          <view>
            <view class="brand-title">刷到的都是自己的</view>
            <view class="brand-sub">Video Knowledge Base</view>
          </view>
        </view>
      </slot>
    </view>

    <view v-if="title" class="nav-title">{{ title }}</view>

    <view class="nav-actions">
      <slot name="actions"></slot>
    </view>
  </view>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: ''
  },
  showBrand: {
    type: Boolean,
    default: false
  }
})
</script>

<style scoped lang="scss">
.app-navbar {
  position: sticky;
  top: 0;
  z-index: 20;
  min-height: 56px;
  padding: 10px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  background: #FFFFFF;
  border-bottom: 1px solid #E7EBF0;
  box-sizing: border-box;
}

.nav-left {
  min-width: 0;
}

.brand {
  display: flex;
  align-items: center;
  gap: 9px;
}

.logo {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  color: #FFFFFF;
  background: #38A169;
  font-size: 13px;
  font-weight: 800;
}

.brand-title {
  color: #222222;
  font-size: 16px;
  font-weight: 900;
  line-height: 1.15;
}

.brand-sub {
  margin-top: 2px;
  color: #888888;
  font-size: 10px;
}

.nav-title {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  color: #222222;
  font-size: 17px;
  font-weight: 900;
}

.nav-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}
</style>
