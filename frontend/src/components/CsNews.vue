<script setup lang="ts">
import { computed, ref } from 'vue'

import { downloadMemo, memoBlocks, memoText } from '../memo'
import type { News } from '../types'
import LockIcon from './LockIcon.vue'

// 고객 문의 처리 과정: 왼쪽은 에이전트들이 남긴 판단을 대화창으로, 오른쪽은 결론을 내려받을 수 있는 메모지로.
const props = defineProps<{ news: News; echo: string | null }>()

const blocks = computed(() => memoBlocks(props.news, props.echo).filter((b) => b.kind !== 'title' && b.kind !== 'rule'))
const status = ref<string | null>(null)
const working = ref(false)

async function save(format: 'png' | 'jpg') {
  working.value = true
  status.value = null
  try {
    await downloadMemo(props.news, props.echo, format)
    status.value = `${format.toUpperCase()} 파일로 저장했어요.`
  } catch {
    status.value = '이미지를 만들지 못했어요. 내용 복사를 이용해 주세요.'
  } finally {
    working.value = false
  }
}

async function copy() {
  try {
    await navigator.clipboard.writeText(memoText(props.news, props.echo))
    status.value = '메모 내용을 복사했어요.'
  } catch {
    status.value = '복사하지 못했어요. 브라우저의 복사 권한을 확인해 주세요.'
  }
}

const short = (agent: string) => agent.replace(' 에이전트', '')
</script>

<template>
  <div class="process">
    <section class="chat" aria-label="에이전트 논의">
      <h3>에이전트 논의</h3>
      <ol>
        <li v-if="echo" class="row me">
          <div class="bubble">{{ echo }}</div>
        </li>
        <li v-for="(d, i) in news.discussion" :key="i" class="row" :style="{ animationDelay: `${i * 90}ms` }">
          <span class="avatar" :data-a="d.agent" aria-hidden="true">{{ short(d.agent).slice(0, 1) }}</span>
          <div class="said">
            <span class="who">{{ d.agent }}</span>
            <div class="bubble">{{ d.text }}</div>
          </div>
        </li>
        <li v-if="news.hidden" class="locked"><LockIcon /><span>내부 논의 {{ news.hidden }}건은 공개하지 않아요</span></li>
      </ol>
    </section>

    <section class="memo-side" aria-label="접수 메모">
      <div class="memo">
        <div class="memo-head">
          <strong>PITCHROOM 접수 메모</strong>
        </div>
        <template v-for="(b, i) in blocks" :key="i">
          <span v-if="b.kind === 'stamp'" class="stamp" :class="news.hold ? 'hold' : 'ok'">{{ b.text }}</span>
          <span v-else-if="b.kind === 'label'" class="label">{{ b.text }}</span>
          <p v-else-if="b.kind === 'bullet'" class="bullet">{{ b.text }}</p>
          <p v-else :class="b.kind">{{ b.text }}</p>
        </template>
      </div>
      <div class="actions">
        <button class="pill-btn dark" type="button" :disabled="working" @click="save('png')">PNG로 저장</button>
        <button class="pill-btn" type="button" :disabled="working" @click="save('jpg')">JPG로 저장</button>
        <button class="pill-btn" type="button" @click="copy">내용 복사</button>
      </div>
      <p class="status" role="status">{{ status }}</p>
    </section>
  </div>
</template>

<style scoped>
.process { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr); gap: 16px; align-items: start; }

/* 대화창 */
.chat { background: var(--surface); border: 1px solid var(--line); border-radius: 22px; padding: 16px 16px 18px; min-width: 0; }
h3 { margin: 0 0 12px; font-family: var(--font-display); font-size: 12px; font-weight: 800; letter-spacing: .08em; color: var(--muted); }
ol { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 12px; }
.row { display: flex; gap: 10px; align-items: flex-start; animation: rise .4s ease both; }
.row.me { justify-content: flex-end; }
.avatar { flex: none; width: 30px; height: 30px; border-radius: 50%; display: grid; place-items: center; font-size: 13px; font-weight: 700; color: var(--muted); background: var(--tile); }
.avatar[data-a="접수 에이전트"] { color: var(--g-blue); background: color-mix(in srgb, var(--g-blue) 14%, transparent); }
.avatar[data-a="피팅 에이전트"] { color: var(--g-green); background: color-mix(in srgb, var(--g-green) 14%, transparent); }
.avatar[data-a="정책 에이전트"] { color: var(--g-red); background: color-mix(in srgb, var(--g-red) 14%, transparent); }
.avatar[data-a="검수 에이전트"], .avatar[data-a="재고 에이전트"] { color: var(--g-yellow); background: color-mix(in srgb, var(--g-yellow) 18%, transparent); }
.said { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.who { font-size: 11.5px; font-weight: 700; color: var(--muted); }
.bubble { font-size: 13.5px; line-height: 1.5; padding: 9px 13px; border-radius: 4px 16px 16px 16px; background: var(--tile); max-width: 100%; overflow-wrap: anywhere; }
.me .bubble { border-radius: 16px 4px 16px 16px; background: var(--fg); color: var(--bg); max-width: 80%; }
.locked { justify-content: center; padding-top: 2px; }

/* 메모지 */
.memo-side { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.memo { position: relative; background: #fff8dc; color: #2b2620; border-radius: 4px 4px 14px 4px; padding: 26px 22px 20px; display: flex; flex-direction: column; gap: 4px; box-shadow: var(--shadow); transform: rotate(-.6deg); }
.memo::before { content: ""; position: absolute; inset: 0 0 auto 0; height: 10px; background: #f3e7b3; border-radius: 4px 4px 0 0; }
.memo-head strong { font-family: var(--font-display); font-size: 16px; }
.memo p { margin: 0; font-size: 14px; line-height: 1.5; overflow-wrap: anywhere; }
.memo .small { font-size: 12px; color: #8a7f6a; }
.memo .small:last-child { margin-top: 12px; padding-top: 10px; border-top: 1px dashed #d9cfae; }
.memo .label { margin-top: 12px; font-size: 11.5px; font-weight: 700; color: #8a7f6a; }
.memo .bullet { padding-left: 14px; position: relative; font-size: 13.5px; }
.memo .bullet::before { content: "•"; position: absolute; left: 2px; }
.stamp { align-self: flex-start; margin-top: 8px; font-size: 12.5px; font-weight: 700; padding: 3px 12px; border-radius: 999px; border: 2px solid; }
.stamp.ok { color: #188038; }
.stamp.hold { color: #b06000; }
.actions { display: flex; gap: 6px; flex-wrap: wrap; }
.status { margin: 0; font-size: 12.5px; color: var(--muted); min-height: 1.2em; }

@media (max-width: 760px) {
  .process { grid-template-columns: minmax(0, 1fr); }
  .memo { transform: none; }
}
</style>
