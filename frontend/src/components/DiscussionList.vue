<script setup lang="ts">
import type { Line } from '../types'
import LockIcon from './LockIcon.vue'

defineProps<{ lines: Line[]; hidden: number }>()
</script>

<template>
  <details class="discuss">
    <summary>에이전트 논의 보기 · 공개 {{ lines.length }}건<template v-if="hidden"> · 비공개 {{ hidden }}건</template></summary>
    <ul>
      <li v-for="(d, i) in lines" :key="i">
        <span class="agent" :data-a="d.agent">{{ d.agent.replace(' 에이전트', '') }}</span>
        <span>{{ d.text }}</span>
      </li>
      <li v-if="hidden" class="locked"><LockIcon /><span>내부 논의 {{ hidden }}건은 공개하지 않아요 (매입가·결재 기준 등)</span></li>
    </ul>
  </details>
</template>

<style scoped>
.discuss { width: min(600px, 100%); text-align: left; font-size: 13px; }
summary { list-style: none; cursor: pointer; color: var(--muted); text-align: center; }
summary::-webkit-details-marker { display: none; }
summary:hover { color: var(--fg); }
ul { list-style: none; margin: 10px 0 0; padding: 12px 14px; display: flex; flex-direction: column; gap: 8px; background: var(--surface); border: 1px solid var(--line); border-radius: 14px; }
li:not(.locked) { display: grid; grid-template-columns: auto 1fr; gap: 10px; align-items: baseline; }
.agent { font-size: 11.5px; font-weight: 700; padding: 2px 8px; border-radius: 6px; white-space: nowrap; color: var(--muted); background: var(--tile); }
.agent[data-a="접수 에이전트"] { color: var(--g-blue); background: color-mix(in srgb, var(--g-blue) 12%, transparent); }
.agent[data-a="피팅 에이전트"] { color: var(--g-green); background: color-mix(in srgb, var(--g-green) 12%, transparent); }
.agent[data-a="정책 에이전트"] { color: var(--g-red); background: color-mix(in srgb, var(--g-red) 12%, transparent); }
.agent[data-a="재고 에이전트"], .agent[data-a="검수 에이전트"] { color: var(--g-yellow); background: color-mix(in srgb, var(--g-yellow) 16%, transparent); }
</style>
