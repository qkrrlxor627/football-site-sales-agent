<script setup lang="ts">
import { ref } from 'vue'

defineProps<{ placeholder: string; busy: boolean }>()
const emit = defineEmits<{ send: [text: string] }>()

const MAX = 500 // 서버 제한과 같게
const text = ref('')
const input = ref<HTMLInputElement | null>(null)

function submit() {
  const t = text.value.trim()
  if (!t) return
  text.value = ''
  emit('send', t)
}

defineExpose({ focus: () => input.value?.focus({ preventScroll: true }) })
</script>

<template>
  <form class="search" autocomplete="off" @submit.prevent="submit">
    <input ref="input" v-model="text" type="text" :maxlength="MAX" :placeholder="placeholder" aria-label="답변 입력" enterkeyhint="send" />
    <button class="send" type="submit" aria-label="보내기" :aria-busy="busy" :disabled="busy">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7" /></svg>
    </button>
  </form>
</template>

<style scoped>
.search { display: flex; align-items: center; gap: 8px; width: min(600px, 100%); background: var(--surface); border: 1px solid var(--line); border-radius: 999px; padding: 6px 6px 6px 20px; box-shadow: var(--shadow); }
.search:focus-within { border-color: var(--accent); }
input { flex: 1; min-width: 0; border: 0; background: none; outline: none; font-size: 16px; padding-block: 8px; }
.send { flex: none; width: 40px; height: 40px; border-radius: 50%; border: 0; background: var(--fg); color: var(--bg); display: grid; place-items: center; }
.send svg { width: 18px; height: 18px; }
</style>
