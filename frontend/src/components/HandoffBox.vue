<script setup lang="ts">
import type { Handoff } from '../types'

defineProps<{ handoff: Handoff }>()
</script>

<template>
  <div class="handoff">
    <strong>{{ handoff.title }}</strong>
    <span>{{ handoff.body }}</span>
    <ul class="alt-list">
      <li v-for="a in handoff.items" :key="a">{{ a }}</li>
    </ul>
  </div>
</template>

<style scoped>
.handoff { width: min(600px, 100%); text-align: left; border: 1px solid var(--line); background: var(--surface); border-radius: 18px; padding: 16px 18px; display: flex; flex-direction: column; gap: 8px; font-size: 13.5px; }
strong { font-family: var(--font-display); font-size: 15px; }
</style>
