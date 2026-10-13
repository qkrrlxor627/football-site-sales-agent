<script setup lang="ts">
import { onBeforeUnmount, watch } from 'vue'

const props = defineProps<{ message: string | null }>()
const emit = defineEmits<{ close: [] }>()

let timer: ReturnType<typeof setTimeout> | undefined
watch(
  () => props.message,
  (m) => {
    clearTimeout(timer)
    if (m) timer = setTimeout(() => emit('close'), 7000)
  },
  { immediate: true },
)
onBeforeUnmount(() => clearTimeout(timer))
</script>

<template>
  <div class="toast-host" role="alert" aria-live="assertive">
    <div v-if="message" class="toast">
      <span>{{ message }}</span>
      <button type="button" aria-label="닫기" @click="emit('close')">×</button>
    </div>
  </div>
</template>

<style scoped>
.toast-host { position: fixed; inset: auto 0 20px 0; display: flex; justify-content: center; padding-inline: 16px; pointer-events: none; z-index: 10; }
.toast { pointer-events: auto; display: flex; align-items: center; gap: 12px; max-width: 560px; background: var(--fg); color: var(--bg); border-radius: 14px; padding: 12px 12px 12px 18px; font-size: 14px; box-shadow: var(--shadow); animation: rise .25s ease both; }
button { background: none; border: 0; color: inherit; font-size: 20px; line-height: 1; padding: 2px 8px; opacity: .7; }
button:hover { opacity: 1; }
</style>
