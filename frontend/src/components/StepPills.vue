<script setup lang="ts">
import type { Step } from '../types'

defineProps<{ steps: Step[] }>()
</script>

<template>
  <ol class="steps" aria-label="주문 진행 단계">
    <li v-for="s in steps" :key="s.text" :class="s.state" :aria-current="s.state === 'now' || s.state === 'svc' ? 'step' : undefined">{{ s.text }}</li>
  </ol>
</template>
