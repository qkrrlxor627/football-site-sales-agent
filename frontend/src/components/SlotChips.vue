<script setup lang="ts">
import type { Slot } from '../types'

defineProps<{ slots: Slot[] }>()
</script>

<template>
  <ul class="slots" aria-label="지금까지 파악한 조건">
    <li v-for="s in slots" :key="s.key" :data-k="s.key" :class="{ on: s.on }"><i aria-hidden="true"></i>{{ s.label }} <b>{{ s.text }}</b></li>
  </ul>
</template>

<style scoped>
.slots { display: flex; flex-wrap: wrap; justify-content: center; gap: 6px 16px; font-size: 13px; color: var(--muted); margin: 0; padding: 0; list-style: none; }
li { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }
i { width: 7px; height: 7px; border-radius: 50%; background: var(--line); }
b { font-weight: 600; color: var(--fg); }
[data-k="surface"].on i { background: var(--g-blue); }
[data-k="width"].on i { background: var(--g-red); }
[data-k="size"].on i { background: var(--g-yellow); }
[data-k="budget"].on i { background: var(--g-green); }
[data-k="style"].on i { background: var(--fg); }
</style>
