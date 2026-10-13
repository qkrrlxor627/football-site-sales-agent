<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { won } from '../format'
import type { Product } from '../types'

const props = defineProps<{ product: Product; sizes: number[]; defaultSize: number; busy: boolean }>()
const emit = defineEmits<{ buy: [size: number]; close: [] }>()

const size = ref(props.sizes.includes(props.defaultSize) ? props.defaultSize : props.sizes[0])
const select = ref<HTMLSelectElement | null>(null)
onMounted(() => select.value?.focus({ preventScroll: true }))
</script>

<template>
  <form class="sheet" aria-label="주문하기" @submit.prevent="emit('buy', size)" @keydown.esc="emit('close')">
    <strong>{{ product.name }} {{ product.stud }} · {{ won(product.price) }}</strong>
    <label>사이즈
      <select ref="select" v-model.number="size">
        <option v-for="z in sizes" :key="z" :value="z">{{ z }}mm</option>
      </select>
    </label>
    <button class="buy" type="submit" :disabled="busy">주문하기 (데모 결제)</button>
    <button class="switch" type="button" @click="emit('close')">취소</button>
  </form>
</template>

<style scoped>
.sheet { width: min(600px, 100%); text-align: left; border: 1px solid var(--line); background: var(--surface); border-radius: 18px; padding: 16px 18px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; font-size: 14px; }
strong { flex: 1 1 200px; font-family: var(--font-display); }
select { border: 1px solid var(--line); border-radius: 10px; padding: 8px 10px; background: var(--bg); font-size: 14px; margin-left: 6px; }
</style>
