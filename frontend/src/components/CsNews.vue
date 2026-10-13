<script setup lang="ts">
import type { News } from '../types'
import LockIcon from './LockIcon.vue'

defineProps<{ news: News }>()
</script>

<template>
  <div class="news" role="group" aria-label="고객 문의 처리 과정" tabindex="0">
    <section class="slide s1">
      <div class="step">문의 <em>1/4</em></div>
      <h3>{{ news.summary }}</h3>
    </section>
    <section class="slide s2">
      <div class="step">에이전트 논의 <em>2/4</em></div>
      <ul>
        <li v-for="(d, i) in news.discussion" :key="i"><span class="ag">{{ d.agent }}</span>{{ d.text }}</li>
      </ul>
      <div v-if="news.hidden" class="locked"><LockIcon /><span>내부 논의 {{ news.hidden }}건 비공개</span></div>
    </section>
    <section class="slide s3">
      <div class="step">적용 규칙 <em>3/4</em></div>
      <ul>
        <li v-for="r in news.rules" :key="r">{{ r }}</li>
      </ul>
    </section>
    <section class="slide s4">
      <div class="step">결론 <em>4/4</em></div>
      <span class="verdict" :class="news.hold ? 'hold' : 'ok'">{{ news.verdict }}</span>
      <p>{{ news.next }}</p>
      <ul v-if="news.options.length" class="alt-list">
        <li v-for="o in news.options" :key="o">{{ o }}</li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.news { display: flex; gap: 14px; overflow-x: auto; scroll-snap-type: x mandatory; padding-bottom: 6px; }
.slide { flex: 1 0 220px; min-height: 280px; scroll-snap-align: start; border-radius: 22px; padding: 18px; display: flex; flex-direction: column; gap: 10px; background: var(--surface); border: 1px solid var(--line); min-width: 0; animation: rise .5s ease both; }
.step { display: flex; justify-content: space-between; font-family: var(--font-display); font-weight: 800; font-size: 12px; letter-spacing: .08em; }
.step em { font-style: normal; color: var(--muted); font-variant-numeric: tabular-nums; }
h3 { margin: 0; font-family: var(--font-display); font-size: 19px; line-height: 1.35; text-wrap: balance; }
p, li { font-size: 13.5px; margin: 0; }
ul:not(.alt-list) { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 8px; }
.ag { display: block; font-size: 11.5px; font-weight: 700; color: var(--muted); }
.s1 { background: color-mix(in srgb, var(--g-blue) 9%, var(--surface)); }
.s1 .step { color: var(--g-blue); }
.s2 .step { color: var(--g-green); }
.s3 .step { color: var(--g-red); }
.s4 .step { color: var(--g-yellow); }
.verdict { align-self: flex-start; font-size: 12.5px; font-weight: 700; padding: 4px 10px; border-radius: 999px; }
.verdict.ok { color: var(--g-green); background: color-mix(in srgb, var(--g-green) 13%, transparent); }
.verdict.hold { color: var(--g-yellow); background: color-mix(in srgb, var(--g-yellow) 16%, transparent); }
</style>
