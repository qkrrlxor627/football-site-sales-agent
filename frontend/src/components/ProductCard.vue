<script setup lang="ts">
import { discount, won } from '../format'
import type { ProductCard } from '../types'
import ShoePhoto from './ShoePhoto.vue'

defineProps<{ card: ProductCard }>()
defineEmits<{ buy: [code: string] }>()
</script>

<template>
  <article class="card" :class="{ best: card.best }">
    <span v-if="card.label" class="best-label" :class="{ quiet: card.quiet }">{{ card.label }}</span>
    <ShoePhoto :src="card.image" :alt="`${card.name} ${card.stud}`" :fallback="card.stud" />
    <div class="meta">
      <span class="stud">{{ card.stud }}</span>
      <span class="code">{{ card.stud_info }}</span>
    </div>
    <div class="name">{{ card.name }}</div>
    <div v-if="card.color" class="color">{{ card.color }}</div>
    <div class="price">
      <template v-if="card.list_price">
        <span class="off">{{ discount(card.price, card.list_price) }}%</span>
        <span class="sr-only">할인가</span>{{ won(card.price) }}
        <s><span class="sr-only">정가</span>{{ won(card.list_price) }}</s>
      </template>
      <template v-else>{{ won(card.price) }}</template>
    </div>
    <div v-if="card.trade" class="trade">
      <span class="sr-only">양보한 조건</span>
      <span v-for="t in card.trade" :key="t" class="chip">{{ t }}</span>
    </div>
    <div v-else class="why">{{ card.why }}</div>
    <div v-if="card.size_note" class="soldout">{{ card.size_note }}</div>
    <button v-if="card.buyable" class="buy" type="button" :disabled="!card.sizes.length" @click="$emit('buy', card.code)">
      {{ card.sizes.length ? '구매하기' : '품절' }}
    </button>
  </article>
</template>

<style scoped>
.color { font-size: 12px; color: var(--muted); margin-top: -4px; }
.price { font-family: var(--font-display); font-weight: 700; font-size: 15px; font-variant-numeric: tabular-nums; display: flex; align-items: baseline; gap: 6px; flex-wrap: wrap; }
.off { color: var(--g-red); }
.price s { font-weight: 500; font-size: 12.5px; color: var(--muted); }
.why { font-size: 12.5px; color: var(--muted); line-height: 1.45; }
.trade { display: flex; flex-direction: column; gap: 4px; }
.chip { font-size: 12.5px; line-height: 1.4; padding: 4px 8px; border-radius: 8px; background: color-mix(in srgb, var(--g-yellow) 14%, transparent); }
.buy { margin-top: 6px; }
.soldout { font-size: 12.5px; font-weight: 600; color: var(--g-red); }
</style>
