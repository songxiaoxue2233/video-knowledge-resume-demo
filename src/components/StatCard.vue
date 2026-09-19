<template>
  <!-- 首页四宫格统计卡片，对应 PC 原型深藏青数据卡。 -->
  <view class="stat-card">
    <view>
      <view class="stat-value">{{ value }}</view>
      <view class="stat-label">{{ label }}</view>
    </view>
    <view class="stat-icon">{{ icon }}</view>
  </view>
</template>

<script setup>
defineProps({
  value: {
    type: [String, Number],
    required: true
  },
  label: {
    type: String,
    required: true
  },
  icon: {
    type: String,
    default: ''
  }
})
</script>

<style scoped lang="scss">
.stat-card {
  min-height: 86px;
  padding: 15px 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-radius: 10px;
  background: #1A2333;
  box-shadow: 0 8px 18px rgba(26, 35, 51, 0.18);
  box-sizing: border-box;
}

.stat-value {
  color: #FFFFFF;
  font-size: 28px;
  line-height: 1;
  font-weight: 900;
}

.stat-label {
  margin-top: 9px;
  color: rgba(255, 255, 255, 0.82);
  font-size: 12px;
}

.stat-icon {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: rgba(255, 255, 255, 0.92);
  background: rgba(255, 255, 255, 0.12);
  font-size: 17px;
}
</style>
