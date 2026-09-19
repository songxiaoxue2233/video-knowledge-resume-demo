<template>
  <view class="oauth-page">
    <web-view :src="targetUrl" />
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'

const targetUrl = ref('')

onLoad((query) => {
  targetUrl.value = decodeURIComponent(query.url || '')
  if (!targetUrl.value) {
    uni.showToast({ title: '授权地址无效', icon: 'none' })
    setTimeout(() => uni.navigateBack(), 800)
  }
})
</script>

<style scoped>
.oauth-page {
  min-height: 100vh;
  background: #fff;
}
</style>
