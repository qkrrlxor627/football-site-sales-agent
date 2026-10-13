<script setup lang="ts">
import type { OrderCard } from '../types'
import ShoePhoto from './ShoePhoto.vue'
import StepPills from './StepPills.vue'

defineProps<{ order: OrderCard }>()
</script>

<template>
  <article class="card" :class="{ best: order.primary }">
    <span v-if="order.primary" class="best-label">지금 볼 주문</span>
    <ShoePhoto :src="order.image" :alt="`${order.name} ${order.stud}`" :fallback="order.stud" />
    <div class="meta">
      <span class="stud">{{ order.stud }}</span>
      <span class="code">{{ order.id }} · {{ order.size }}mm</span>
    </div>
    <div class="name">{{ order.name }}</div>
    <StepPills :steps="order.steps" />
    <div class="note">
      {{ order.when }}<template v-if="order.exchanges"> · 교환 {{ order.exchanges }}회</template>
      <template v-if="order.note"><br />{{ order.note }}</template>
    </div>
  </article>
</template>

<style scoped>
.note { font-size: 12.5px; color: var(--muted); line-height: 1.45; }
</style>
