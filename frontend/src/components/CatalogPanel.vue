<script setup lang="ts">
import { computed, ref } from 'vue'

import { useSession } from '../stores/session'
import ProductCard from './ProductCard.vue'

// 전체 상품 둘러보기. 여기서는 고르기만 하고, 어느 신발이 내 구장에 안전한지는 상담(규칙)이 판단한다.
const s = useSession()
const surface = ref<string | null>(null)
const line = ref<string | null>(null)
const saleOnly = ref(false)

const products = computed(() =>
  (s.catalog?.products ?? []).filter(
    (p) => (!surface.value || p.surfaces.includes(surface.value)) && (!line.value || p.line === line.value) && (!saleOnly.value || p.list_price !== null),
  ),
)
</script>

<template>
  <div class="head">
    <h2>전체 축구화 <span class="n">{{ products.length }}</span></h2>
    <button class="switch" type="button" @click="s.panel = null">닫기</button>
  </div>
  <div class="filters">
    <div class="group" role="group" aria-label="구장으로 거르기">
      <button class="chip" :class="{ on: surface === null }" type="button" :aria-pressed="surface === null" @click="surface = null">모든 구장</button>
      <button v-for="x in s.catalog?.surfaces" :key="x" class="chip" :class="{ on: surface === x }" type="button" :aria-pressed="surface === x" @click="surface = surface === x ? null : x">{{ x }}</button>
    </div>
    <div class="group" role="group" aria-label="라인으로 거르기">
      <button v-for="x in s.catalog?.lines" :key="x" class="chip" :class="{ on: line === x }" type="button" :aria-pressed="line === x" @click="line = line === x ? null : x">{{ x }}</button>
      <button class="chip sale" :class="{ on: saleOnly }" type="button" :aria-pressed="saleOnly" @click="saleOnly = !saleOnly">할인 중</button>
    </div>
  </div>
  <p v-if="surface">{{ surface }}에 그대로 신을 수 있는 스터드만 보여요. 발볼·예산까지 맞추려면 아래 상담창에 말씀해 주세요.</p>
  <p v-if="!products.length">조건에 맞는 축구화가 없어요.</p>
  <div class="grid">
    <ProductCard v-for="p in products" :key="p.code" :card="p" @buy="s.requestBuy" />
  </div>
</template>

<style scoped>
.head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.n { color: var(--muted); font-weight: 500; }
.filters { display: flex; flex-direction: column; gap: 8px; }
.group { display: flex; gap: 6px; flex-wrap: wrap; }
.chip { background: none; border: 1px solid var(--line); border-radius: 999px; padding: 5px 12px; font-size: 13px; color: var(--muted); }
.chip:hover { border-color: var(--muted); color: var(--fg); }
.chip.on { background: var(--fg); border-color: var(--fg); color: var(--bg); }
.chip.sale.on { background: var(--g-red); border-color: var(--g-red); color: #fff; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 12px; max-height: min(70vh, 760px); overflow-y: auto; padding: 4px; margin: -4px; }
.grid :deep(.card) { animation: none; }
</style>
