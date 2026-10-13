<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import { useAdmin } from '../stores/admin'
import { won } from '../format'
import type { AdminOrder, AdminProduct } from '../types'

const admin = useAdmin()
const tab = ref<'work' | 'products' | 'customers'>('work')
const filter = ref<'todo' | 'all'>('todo')
const sizes = reactive<Record<string, number | undefined>>({}) // 교환해 보낼 사이즈 (주문별)
const edits = reactive<Record<string, { price: number; stock: Record<number, number> }>>({}) // 상품별 수정 중인 값
const temp = ref<{ id: string; password: string } | null>(null) // 방금 만든 임시 비밀번호 (한 번만 보여준다)
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

const sizesFor = (o: AdminOrder) => (admin.board?.products.find((p) => p.code === o.code)?.stock ?? []).filter((x) => x.qty > 0 || x.size === o.size)

async function setStatus(o: AdminOrder, to: string, needsSize: boolean) {
  if (await admin.setStatus(o.id, to, notes[o.id], needsSize ? sizes[o.id] : undefined)) {
    delete notes[o.id]
    delete sizes[o.id]
  }
}

/** 상품 한 줄의 수정용 사본. 처음 손댈 때 지금 값으로 만든다. */
function draft(p: AdminProduct) {
  return (edits[p.code] ??= { price: p.price, stock: Object.fromEntries(p.stock.map((x) => [x.size, x.qty])) })
}
const dirty = (p: AdminProduct) => {
  const e = edits[p.code]
  return !!e && (e.price !== p.price || p.stock.some((x) => e.stock[x.size] !== x.qty))
}
async function saveProduct(p: AdminProduct) {
  const e = edits[p.code]
  const stock = Object.fromEntries(p.stock.filter((x) => e.stock[x.size] !== x.qty).map((x) => [x.size, e.stock[x.size]]))
  if (await admin.updateProduct(p.code, { price: e.price !== p.price ? e.price : undefined, stock })) delete edits[p.code]
}
async function resetPassword(id: string) {
  temp.value = null
  const password = await admin.resetPassword(id)
  if (password) temp.value = { id, password }
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

      <div class="tabs" role="tablist" aria-label="관리 메뉴">
        <button type="button" role="tab" :aria-selected="tab === 'work'" @click="tab = 'work'">할 일</button>
        <button type="button" role="tab" :aria-selected="tab === 'products'" @click="tab = 'products'">상품·재고</button>
        <button type="button" role="tab" :aria-selected="tab === 'customers'" @click="tab = 'customers'">고객 {{ admin.board.customers.length }}</button>
      </div>

      <template v-if="tab === 'work'">
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
          <p :class="h.contact ? 'reach' : 'muted'">{{ h.contact ? `연락처: ${h.contact}` : '연락처를 아직 남기지 않았어요.' }}</p>
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
              <span class="status" :class="{ svc: ['교환 접수', '반품 접수', '사장님 확인 중', '주문 취소'].includes(o.status) }">{{ o.status }}</span>
              <span class="muted">{{ o.account_name }} ({{ o.account_id }})</span>
            </div>
            <span>{{ o.title }}</span>
            <span class="muted">{{ when(o) }}<template v-if="o.exchanges"> · 교환 {{ o.exchanges }}회</template></span>
            <span v-if="o.note" class="muted">고객 안내: {{ o.note }}</span>
          </div>
          <div v-if="o.actions.length" class="act">
            <input v-if="o.actions.length > 1" v-model="notes[o.id]" type="text" maxlength="200" placeholder="고객에게 보일 안내 (비우면 기본 문구)" :aria-label="`${o.id} 고객 안내`" />
            <template v-for="a in o.actions" :key="a.to">
              <label v-if="a.needs_size" class="size">보낼 사이즈
                <select v-model.number="sizes[o.id]" :aria-label="`${o.id} 교환해 보낼 사이즈`">
                  <option :value="undefined" disabled>선택</option>
                  <option v-for="x in sizesFor(o)" :key="x.size" :value="x.size" :disabled="x.qty === 0">{{ x.size }}mm{{ x.size === o.size ? ' (지금)' : '' }} · {{ x.qty }}켤레</option>
                </select>
              </label>
              <button class="pill-btn" :class="{ dark: !['요청 거절', '주문 취소'].includes(a.label) }" type="button" :disabled="admin.busy || (a.needs_size && !sizes[o.id])" @click="setStatus(o, a.to, a.needs_size)">{{ a.label }}</button>
            </template>
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

      <template v-else-if="tab === 'products'">
        <p class="muted">가격·재고를 바꾸면 다음 추천부터 바로 쓰여요. 판매를 멈춘 상품은 추천과 구매에서 빠지고, 지난 주문에는 그대로 보여요.</p>
        <ul class="products">
          <li v-for="p in admin.board.products" :key="p.code" class="product" :class="{ off: !p.active }">
            <div class="row">
              <b>{{ p.code }}</b><span>{{ p.name }} {{ p.stud }}</span><span class="muted">발볼 {{ p.width }}</span>
              <span v-if="!p.active" class="status svc">판매 중지</span>
            </div>
            <div class="row">
              <label class="price">가격
                <input v-model.number="draft(p).price" type="number" min="1000" max="5000000" step="1000" :aria-label="`${p.code} 가격`" />
              </label>
              <span class="muted">지금 {{ won(p.price) }}</span>
            </div>
            <div class="stock" role="group" :aria-label="`${p.code} 사이즈별 재고`">
              <label v-for="x in p.stock" :key="x.size" :class="{ zero: draft(p).stock[x.size] === 0 }">{{ x.size }}
                <input v-model.number="draft(p).stock[x.size]" type="number" min="0" max="999" :aria-label="`${p.code} ${x.size}mm 재고`" />
              </label>
            </div>
            <div class="act">
              <button class="pill-btn dark" type="button" :disabled="admin.busy || !dirty(p)" @click="saveProduct(p)">저장</button>
              <button class="pill-btn" type="button" :disabled="admin.busy" @click="admin.updateProduct(p.code, { active: !p.active })">{{ p.active ? '판매 중지' : '다시 판매' }}</button>
            </div>
          </li>
        </ul>
      </template>

      <template v-else>
        <p class="muted">고객이 비밀번호를 잊었으면 임시 비밀번호를 만들어 전해 주세요. 만든 비밀번호는 여기에 한 번만 보여요.</p>
        <p v-if="temp" class="temp" role="status">{{ temp.id }} 임시 비밀번호: <code>{{ temp.password }}</code> <button class="switch" type="button" @click="temp = null">가리기</button></p>
        <p v-if="!admin.board.customers.length" class="muted">아직 고객이 없어요.</p>
        <ul class="orders">
          <li v-for="c in admin.board.customers" :key="c.id" class="order">
            <div class="info">
              <div class="row"><b>{{ c.name }}</b><span class="muted">{{ c.id }}</span><span v-if="!c.has_password" class="status">데모</span></div>
              <span class="muted">주문 {{ c.orders }}건 · {{ c.contact ?? '연락처 없음' }}<template v-if="c.created_at"> · 가입 {{ stamp(c.created_at).slice(0, 10) }}</template></span>
            </div>
            <div v-if="c.has_password" class="act">
              <button class="pill-btn" type="button" :disabled="admin.busy" @click="resetPassword(c.id)">임시 비밀번호 만들기</button>
            </div>
          </li>
        </ul>
      </template>
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
.tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--line); }
.tabs button { background: none; border: 0; padding: 8px 12px; font-size: 14px; font-weight: 600; color: var(--muted); border-bottom: 2px solid transparent; margin-bottom: -1px; }
.tabs button[aria-selected="true"] { color: var(--fg); border-bottom-color: var(--fg); }
.reach { font-weight: 600; }
.size { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; color: var(--muted); }
.size select, .price input, .stock input { border: 1px solid var(--line); border-radius: 10px; padding: 6px 8px; background: var(--bg); font-size: 14px; color: var(--fg); }
.products { display: flex; flex-direction: column; gap: 10px; }
.product { background: var(--tile); border-radius: 16px; padding: 12px 14px; display: flex; flex-direction: column; gap: 8px; font-size: 14px; }
.product.off { opacity: .7; }
.price { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; color: var(--muted); }
.price input { width: 120px; }
.stock { display: grid; grid-template-columns: repeat(auto-fill, minmax(64px, 1fr)); gap: 6px; }
.stock label { display: flex; flex-direction: column; gap: 2px; font-size: 11.5px; color: var(--muted); }
.stock input { width: 100%; }
.stock .zero input { border-color: var(--g-red); color: var(--g-red); }
.temp { margin: 0; padding: 10px 14px; border-radius: 12px; background: color-mix(in srgb, var(--g-yellow) 14%, transparent); font-size: 14px; }
.temp code { font-size: 15px; font-weight: 700; user-select: all; }
.history ul { margin-top: 8px; display: flex; flex-direction: column; gap: 4px; font-size: 13px; }
</style>
