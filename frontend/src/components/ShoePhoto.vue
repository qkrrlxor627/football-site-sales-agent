<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{ src: string | null; alt: string; fallback: string }>()

// 사진이 없거나 못 불러오면 스터드 글자만 보여준다 (카드가 깨져 보이지 않게).
const failed = ref(false)
watch(() => props.src, () => (failed.value = false))
</script>

<template>
  <div class="shoe">
    <img v-if="src && !failed" :src="src" :alt="alt" loading="lazy" decoding="async" @error="failed = true" />
    <span v-else class="no-photo" role="img" :aria-label="alt">{{ fallback }}</span>
  </div>
</template>
