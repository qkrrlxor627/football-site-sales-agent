<script setup lang="ts">
import { ref } from 'vue'

import { useSession } from '../stores/session'
import type { Account } from '../types'
import ShoePhoto from './ShoePhoto.vue'
import StepPills from './StepPills.vue'

defineProps<{ account: Account }>()

const s = useSession()
const current = ref('')
const next = ref('')
const result = ref<{ ok: boolean; text: string } | null>(null)
const saving = ref(false)

async function change() {
  saving.value = true
  const failed = await s.changePassword(current.value, next.value)
  saving.value = false
  result.value = failed ? { ok: false, text: failed } : { ok: true, text: '비밀번호를 바꿨어요.' }
  if (!failed) current.value = next.value = ''
}
</script>

<template>
  <h2>{{ account.name }}님 주문 {{ account.orders.length }}건</h2>
  <p>배송·교환·반품을 물어보면 이 주문 기록으로 바로 판단해요.</p>
  <ul class="orders">
    <li v-for="o in account.orders" :key="o.id" class="order">
      <ShoePhoto class="thumb" :src="o.image" alt="" :fallback="o.stud" />
      <div class="info">
        <b>{{ o.label }}</b>
        <span>{{ o.id }} · {{ o.when }}<template v-if="o.exchanges"> · 교환 {{ o.exchanges }}회</template></span>
        <StepPills :steps="o.steps" />
        <span v-if="o.note">{{ o.note }}</span>
      </div>
    </li>
  </ul>
  <p v-if="!account.orders.length">아직 주문이 없어요.</p>
  <details class="pw">
    <summary>비밀번호 바꾸기</summary>
    <form @submit.prevent="change">
      <input type="text" name="username" :value="account.id" autocomplete="username" hidden />
      <label>지금 비밀번호 <input v-model="current" type="password" autocomplete="current-password" maxlength="72" /></label>
      <label>새 비밀번호 <input v-model="next" type="password" autocomplete="new-password" maxlength="72" placeholder="8자 이상" /></label>
      <button class="pill-btn dark" type="submit" :disabled="saving || !current || next.length < 8">바꾸기</button>
    </form>
    <p v-if="result" :class="result.ok ? 'ok' : 'bad'" role="status">{{ result.text }}</p>
  </details>
</template>

<style scoped>
.orders { display: flex; flex-direction: column; gap: 10px; margin: 0; padding: 0; list-style: none; }
.order { display: grid; grid-template-columns: 96px 1fr; gap: 14px; align-items: center; padding: 10px; border-radius: 16px; background: var(--tile); }
.thumb { margin: 0; }
.info { min-width: 0; display: flex; flex-direction: column; gap: 4px; font-size: 13px; }
.info b { font-family: var(--font-display); font-size: 14px; }
.pw summary { cursor: pointer; font-size: 13px; color: var(--muted); }
.pw form { display: flex; gap: 10px; flex-wrap: wrap; align-items: flex-end; margin-top: 10px; }
.pw label { flex: 1 1 180px; display: flex; flex-direction: column; gap: 4px; font-size: 12.5px; color: var(--muted); }
.pw input { border: 1px solid var(--line); border-radius: 12px; padding: 9px 12px; background: var(--bg); font-size: 16px; color: var(--fg); }
.pw p.ok.ok { color: var(--g-green); margin-top: 8px; }
.pw p.bad.bad { color: var(--g-red); margin-top: 8px; }
</style>
