<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{ saved: string | null; busy: boolean }>()
const emit = defineEmits<{ save: [contact: string] }>()

// 사람이 이어받는 건: 담당자가 먼저 연락할 수 있게 전화번호나 이메일을 받는다. 이미 남겼으면 보여주고 바꿀 수 있게 한다.
const editing = ref(!props.saved)
const value = ref('')
watch(() => props.saved, (v) => (editing.value = !v))
</script>

<template>
  <div class="contact">
    <template v-if="saved && !editing">
      <span>담당자가 <b>{{ saved }}</b>(으)로 연락드릴게요.</span>
      <button class="switch" type="button" @click="editing = true">바꾸기</button>
    </template>
    <form v-else @submit.prevent="emit('save', value)">
      <label for="contact-input">담당자가 연락드릴 전화번호나 이메일을 남겨 주세요.</label>
      <div class="row">
        <input id="contact-input" v-model="value" type="text" maxlength="60" inputmode="email" autocomplete="tel" placeholder="010-1234-5678" />
        <button class="pill-btn dark" type="submit" :disabled="busy || value.trim().length < 5">남기기</button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.contact { width: min(600px, 100%); text-align: left; border: 1px solid var(--line); background: var(--surface); border-radius: 18px; padding: 14px 18px; font-size: 13.5px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
form { display: flex; flex-direction: column; gap: 8px; width: 100%; }
.row { display: flex; gap: 8px; flex-wrap: wrap; }
input { flex: 1 1 200px; min-width: 0; border: 1px solid var(--line); border-radius: 12px; padding: 9px 14px; background: var(--bg); font-size: 16px; }
</style>
