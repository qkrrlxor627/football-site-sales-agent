<script setup lang="ts">
import type { Account } from '../types'
import ShoePhoto from './ShoePhoto.vue'
import StepPills from './StepPills.vue'

defineProps<{ account: Account }>()
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
</template>

<style scoped>
.orders { display: flex; flex-direction: column; gap: 10px; margin: 0; padding: 0; list-style: none; }
.order { display: grid; grid-template-columns: 96px 1fr; gap: 14px; align-items: center; padding: 10px; border-radius: 16px; background: var(--tile); }
.thumb { margin: 0; }
.info { min-width: 0; display: flex; flex-direction: column; gap: 4px; font-size: 13px; }
.info b { font-family: var(--font-display); font-size: 14px; }
</style>
