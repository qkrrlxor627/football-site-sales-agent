<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import { useAdmin } from '../stores/admin'
import type { AdminOrder } from '../types'

const admin = useAdmin()
const filter = ref<'todo' | 'all'>('todo')
const notes = reactive<Record<string, string>>({}) // 주문·넘어온 건별 메모 입력값

// 다른 창에서 들어온 주문·문의가 보이도록 30초마다 조용히 새로 받는다.
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  admin.load()
  timer = setInterval(() => admin.load(true), 30_000)
})
onBeforeUnmount(() => clearInterval(timer))

const orders = computed(() => (admin.board?.orders ?? []).filter((o) => filter.value === 'all' || o.actions.length > 0))
const tiles = computed(() => {
  const s = admin.board?.summary
  if (!s) return []
  return [
    { label: '넘어온 건', value: s.open_handoffs, alert: s.open_handoffs > 0 },
    { label: '출고 대기', value: s.to_ship, alert: false },
    { label: '배송 중', value: s.shipping, alert: false },
    { label: '교환·반품 진행', value: s.in_service, alert: false },
    { label: '전체 주문', value: s.orders, alert: false },
    { label: '고객', value: s.customers, alert: false },
  ]
})

const when = (o: AdminOrder) => (o.delivered_at ? `배송 완료 ${o.delivered_at}` : o.shipped_at ? `출고 ${o.shipped_at}` : `주문 ${o.ordered_at}`)
const stamp = (iso: string) => iso.replace('T', ' ').slice(0, 16)

async function setStatus(o: AdminOrder, to: string) {
  if (await admin.setStatus(o.id, to, notes[o.id])) delete notes[o.id]
}
async function resolve(id: number) {
  const key = `h${id}`
  if (await admin.resolve(id, notes[key] ?? '')) delete notes[key]
}
</script>

<template>
  <section class="admin" aria-label="관리 화면" :aria-busy="admin.busy">
    <div class="head">
      <h1>관리</h1>
      <button class="pill-btn" type="button" :disabled="admin.busy" @click="admin.load()">새로고침</button>
    </div>
    <p v-if="admin.error" class="err" role="alert">{{ admin.error }}</p>

    <p v-if="!admin.board && !admin.error" class="muted">불러오는 중…</p>
    <template v-if="admin.board">
      <dl class="tiles">
        <div v-for="t in tiles" :key="t.label" :class="{ alert: t.alert }">
          <dt>{{ t.label }}</dt>
          <dd>{{ t.value }}</dd>
        </div>
      </dl>

      <h2>넘어온 건 <span class="n">{{ admin.board.handoffs.length }}</span></h2>
      <p v-if="!admin.board.handoffs.length" class="muted">지금 사람이 봐야 할 건이 없어요.</p>
      <ul class="handoffs">
        <li v-for="h in admin.board.handoffs" :key="h.id" class="handoff">
          <div class="row">
            <span class="kind" :data-kind="h.kind">{{ h.kind_label }}</span>
            <span class="muted">{{ stamp(h.created_at) }} · {{ h.account_name ? `${h.account_name} (${h.account_id})` : '비로그인 고객' }}</span>
          </div>
          <strong>{{ h.summary }}</strong>
          <p class="quote">“{{ h.detail.text }}”</p>
          <p v-if="h.detail.order" class="muted">주문: {{ h.order_id }} · {{ h.detail.order }}</p>
          <p v-if="h.detail.conditions.length" class="muted">조건: {{ h.detail.conditions.join(' · ') }}</p>
          <ul v-if="h.detail.rules.length" class="rules">
            <li v-for="r in h.detail.rules" :key="r">{{ r }}</li>
          </ul>
          <details>
            <summary>에이전트 논의 {{ h.detail.discussion.length }}건 (내부 포함)</summary>
            <ul class="disc">
              <li v-for="(d, i) in h.detail.discussion" :key="i" :class="{ internal: d.internal }">
                <b>{{ d.agent }}</b>{{ d.text }}
              </li>
            </ul>
          </details>
          <p v-if="h.order_id" class="muted">아래 주문 목록에서 {{ h.order_id }}를 승인하거나 거절하면 이 건도 함께 닫혀요.</p>
          <form v-else class="act" @submit.prevent="resolve(h.id)">
            <input v-model="notes[`h${h.id}`]" type="text" maxlength="200" placeholder="처리 메모 (예: 전화 상담 완료)" :aria-label="`${h.summary} 처리 메모`" />
            <button class="pill-btn dark" type="submit" :disabled="admin.busy">처리 완료</button>
          </form>
        </li>
      </ul>

      <div class="head">
        <h2>주문 <span class="n">{{ orders.length }}</span></h2>
        <div class="filters" role="group" aria-label="주문 보기">
          <button class="pill-btn" :class="{ dark: filter === 'todo' }" type="button" :aria-pressed="filter === 'todo'" @click="filter = 'todo'">처리할 주문</button>
          <button class="pill-btn" :class="{ dark: filter === 'all' }" type="button" :aria-pressed="filter === 'all'" @click="filter = 'all'">전체</button>
        </div>
      </div>
      <p v-if="!orders.length" class="muted">{{ filter === 'todo' ? '처리할 주문이 없어요.' : '주문이 없어요.' }}</p>
      <ul class="orders">
        <li v-for="o in orders" :key="o.id" class="order">
          <div class="info">
            <div class="row">
              <b>{{ o.id }}</b>
              <span class="status" :class="{ svc: ['교환 접수', '반품 접수', '사장님 확인 중'].includes(o.status) }">{{ o.status }}</span>
              <span class="muted">{{ o.account_name }} ({{ o.account_id }})</span>
            </div>
            <span>{{ o.title }}</span>
            <span class="muted">{{ when(o) }}<template v-if="o.exchanges"> · 교환 {{ o.exchanges }}회</template></span>
            <span v-if="o.note" class="muted">고객 안내: {{ o.note }}</span>
          </div>
          <div v-if="o.actions.length" class="act">
            <input v-if="o.actions.length > 1" v-model="notes[o.id]" type="text" maxlength="200" placeholder="고객에게 보일 안내 (비우면 기본 문구)" :aria-label="`${o.id} 고객 안내`" />
            <button v-for="a in o.actions" :key="a.to" class="pill-btn" :class="{ dark: a.label !== '요청 거절' }" type="button" :disabled="admin.busy" @click="setStatus(o, a.to)">{{ a.label }}</button>
          </div>
        </li>
      </ul>

      <details v-if="admin.board.done.length" class="history">
        <summary>최근 처리한 건 {{ admin.board.done.length }}건</summary>
        <ul>
          <li v-for="h in admin.board.done" :key="h.id">
            <span class="muted">{{ stamp(h.resolved_at ?? h.created_at) }}</span> {{ h.kind_label }} · {{ h.summary }} → {{ h.resolution }}
          </li>
        </ul>
      </details>
    </template>
  </section>
</template>

<style scoped>
.admin { border: 1px solid var(--line); border-radius: 28px; background: var(--surface); padding: 22px 20px 26px; display: flex; flex-direction: column; gap: 14px; }
.head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
h1, h2 { margin: 0; font-family: var(--font-display); }
h1 { font-size: 22px; }
h2 { font-size: 17px; margin-top: 8px; }
.n { color: var(--muted); font-weight: 500; }
.muted { color: var(--muted); font-size: 13px; margin: 0; }
.err { color: var(--g-red); margin: 0; font-size: 14px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; margin: 0; }
.tiles div { background: var(--tile); border-radius: 16px; padding: 12px 14px; }
.tiles dt { font-size: 12px; color: var(--muted); }
.tiles dd { margin: 0; font-family: var(--font-display); font-weight: 800; font-size: 24px; font-variant-numeric: tabular-nums; }
.tiles .alert { background: color-mix(in srgb, var(--g-red) 10%, var(--surface)); }
.tiles .alert dd { color: var(--g-red); }
ul { list-style: none; margin: 0; padding: 0; }
.handoffs, .orders { display: flex; flex-direction: column; gap: 10px; }
.handoff { border: 1px solid var(--line); border-radius: 18px; padding: 14px 16px; display: flex; flex-direction: column; gap: 8px; font-size: 14px; }
.handoff p { margin: 0; }
.row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.kind, .status { font-size: 11.5px; font-weight: 700; padding: 2px 8px; border-radius: 999px; background: var(--tile); white-space: nowrap; }
.kind[data-kind="health"], .status.svc { color: var(--g-red); background: color-mix(in srgb, var(--g-red) 12%, transparent); }
.kind[data-kind="policy"] { color: var(--g-yellow); background: color-mix(in srgb, var(--g-yellow) 16%, transparent); }
.quote { color: var(--fg); overflow-wrap: anywhere; }
.rules { display: flex; flex-direction: column; gap: 2px; font-size: 13px; }
details summary { cursor: pointer; color: var(--muted); font-size: 13px; }
.disc { margin-top: 8px; display: flex; flex-direction: column; gap: 6px; font-size: 13px; }
.disc b { display: block; font-size: 11.5px; color: var(--muted); }
.disc .internal { border-left: 2px solid var(--g-yellow); padding-left: 8px; }
.order { display: flex; gap: 12px; justify-content: space-between; align-items: center; flex-wrap: wrap; background: var(--tile); border-radius: 16px; padding: 12px 14px; font-size: 14px; }
.info { display: flex; flex-direction: column; gap: 3px; min-width: 0; flex: 1 1 260px; }
.act { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.act input { flex: 1 1 220px; min-width: 0; border: 1px solid var(--line); border-radius: 10px; padding: 7px 12px; background: var(--bg); font-size: 14px; }
.filters { display: flex; gap: 6px; }
.history ul { margin-top: 8px; display: flex; flex-direction: column; gap: 4px; font-size: 13px; }
</style>
