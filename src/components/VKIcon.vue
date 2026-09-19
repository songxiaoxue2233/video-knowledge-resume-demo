<template>
  <svg class="vk-icon" :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path v-for="(d, index) in paths" :key="index" :d="d" />
    <circle v-for="(c, index) in circles" :key="'c' + index" :cx="c[0]" :cy="c[1]" :r="c[2]" />
    <line v-for="(l, index) in lines" :key="'l' + index" :x1="l[0]" :y1="l[1]" :x2="l[2]" :y2="l[3]" />
  </svg>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ name: { type: String, default: 'home' }, size: { type: [Number, String], default: 22 } })

const iconMap = {
  home: { paths: ['M3 10.5 12 3l9 7.5', 'M5 10v10h14V10', 'M9 20v-6h6v6'] },
  link: { paths: ['M10 13a5 5 0 0 0 7.1 0l2-2a5 5 0 0 0-7.1-7.1l-1.1 1.1', 'M14 11a5 5 0 0 0-7.1 0l-2 2a5 5 0 0 0 7.1 7.1l1.1-1.1'] },
  book: { paths: ['M4 5.5A2.5 2.5 0 0 1 6.5 3H20v17H6.5A2.5 2.5 0 0 0 4 22V5.5Z', 'M4 5.5A2.5 2.5 0 0 1 6.5 8H20'] },
  user: { paths: ['M20 21a8 8 0 0 0-16 0'], circles: [[12, 8, 4]] },
  search: { circles: [[11, 11, 7]], lines: [[16, 16, 21, 21]] },
  bell: { paths: ['M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9', 'M13.7 21a2 2 0 0 1-3.4 0'] },
  help: { paths: ['M9.1 9a3 3 0 1 1 5.8 1c-.9 1.3-2.4 1.8-2.9 3'], circles: [[12, 19, 0.8], [12, 12, 10]] },
  feedback: { paths: ['M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4v8Z'] },
  camera: { paths: ['M14.5 4 16 7h3a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h3l1.5-3h5Z'], circles: [[12, 13, 4]] },
  chart: { paths: ['M4 20V10', 'M10 20V4', 'M16 20v-7', 'M22 20H2'] },
  star: { paths: ['m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3 6.4 20.2 7.5 14 3 9.6l6.2-.9L12 3Z'] },
  clock: { circles: [[12, 12, 9]], paths: ['M12 7v5l3 2'] },
  tag: { paths: ['M20.6 13.2 13.2 20.6a2 2 0 0 1-2.8 0L3 13.2V3h10.2l7.4 7.4a2 2 0 0 1 0 2.8Z'], circles: [[7.5, 7.5, 1]] },
  filter: { paths: ['M4 6h16', 'M7 12h10', 'M10 18h4'] },
  bookmark: { paths: ['M6 4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18l-6-3-6 3V4Z'] },
  arrow: { paths: ['M5 12h14', 'm13 6 6 6-6 6'] },
  back: { paths: ['M19 12H5', 'm11 18-6-6 6-6'] },
  more: { circles: [[5, 12, 1], [12, 12, 1], [19, 12, 1]] },
  heart: { paths: ['M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21l7.8-7.6 1-1a5.5 5.5 0 0 0 0-7.8Z'] },
  shield: { paths: ['M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z'] },
  zap: { paths: ['M13 2 3 14h8l-1 8 11-14h-8l1-6Z'] },
  info: { circles: [[12, 12, 10]], paths: ['M12 16v-4', 'M12 8h.01'] },
  check: { paths: ['m20 6-11 11-5-5'] },
  x: { paths: ['M18 6 6 18', 'M6 6l12 12'] },
  chevron: { paths: ['m9 18 6-6-6-6'] },
  edit: { paths: ['M12 20h9', 'M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5Z'] },
  sparkle: { paths: ['M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z', 'M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z'] },
  play: { paths: ['M8 5v14l11-7-11-7Z'] }
}

const current = computed(() => iconMap[props.name] || iconMap.home)
const paths = computed(() => current.value.paths || [])
const circles = computed(() => current.value.circles || [])
const lines = computed(() => current.value.lines || [])
</script>

<style scoped>
.vk-icon { display: block; }
</style>
