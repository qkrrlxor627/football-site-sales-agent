<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'

import { useSession } from '../stores/session'
import type { View } from '../types'
import AskBar from './AskBar.vue'
import ContactForm from './ContactForm.vue'
import CsNews from './CsNews.vue'
import DiscussionList from './DiscussionList.vue'
import HandoffBox from './HandoffBox.vue'
import OrderCard from './OrderCard.vue'
import ProductCard from './ProductCard.vue'
import PurchaseSheet from './PurchaseSheet.vue'
import SlotChips from './SlotChips.vue'

const props = defineProps<{ view: View }>()
const s = useSession()
const askBar = ref<InstanceType<typeof AskBar> | null>(null)

const MAX_BLUR = 12
// 답할수록 뒤의 진열대가 선명해진다: 서버가 준 blur(0~12) 하나로 흐림·밝기·채도를 같이 움직인다.
const shelfStyle = computed(() => {
  const prog = 1 - Math.min(props.view.shelf.blur, MAX_BLUR) / MAX_BLUR
  return { '--blur': `${props.view.shelf.blur}px`, '--dim': `${0.42 + prog * 0.58}`, '--sat': `${0.7 + prog * 0.3}` }
})
const fillers = computed(() => (props.view.shelf.kind === 'products' ? Math.max(0, 3 - props.view.shelf.cards.length) : 0))
const headline = computed(() => (s.busy ? '에이전트들이 논의하는 중…' : props.view.headline))
const long = computed(() => !s.busy && props.view.headline.length > 40)
const showDiscussion = computed(() => !props.view.news && (props.view.discussion.length > 0 || props.view.hidden > 0))

async function send(text: string) {
  await s.send(text)
  await nextTick()
  askBar.value?.focus()
}
</script>

<template>
  <section class="stage" :class="{ collect: view.collect, photo: !!view.background }" :aria-busy="s.busy">
    <Transition name="bg">
      <div v-if="view.background" :key="view.background" class="bg" :style="{ backgroundImage: `url(${view.background})` }" aria-hidden="true"></div>
    </Transition>
    <svg class="pitch" viewBox="0 0 1000 420" preserveAspectRatio="none" aria-hidden="true">
      <rect x="6" y="6" width="988" height="408" rx="26" /><line x1="500" y1="6" x2="500" y2="414" />
      <circle cx="500" cy="210" r="78" /><rect x="6" y="110" width="120" height="200" /><rect x="874" y="110" width="120" height="200" />
    </svg>

    <div class="shelf-wrap">
      <div class="count">{{ view.count.prefix }}<b v-if="view.count.strong">{{ view.count.strong }}</b>{{ view.count.suffix }}</div>
      <CsNews v-if="view.news" :news="view.news" :echo="view.echo" />
      <div v-else class="shelf" :class="{ paused: view.shelf.paused }" :style="shelfStyle" :inert="view.collect && view.shelf.blur > 0">
        <template v-if="view.shelf.kind === 'products'">
          <ProductCard v-for="c in view.shelf.cards" :key="c.code" :card="c" @buy="s.requestBuy" />
        </template>
        <template v-else-if="view.shelf.kind === 'orders'">
          <OrderCard v-for="o in view.shelf.cards" :key="o.id" :order="o" />
        </template>
        <div v-for="i in fillers" :key="`empty-${i}`" class="card empty">{{ view.shelf.empty_text }}</div>
      </div>
    </div>

    <div class="ask">
      <p v-if="view.echo" class="echo">“{{ view.echo }}”</p>
      <h1 class="q" :class="{ long }" aria-live="polite">{{ headline }}</h1>
      <AskBar ref="askBar" :placeholder="view.placeholder" :busy="s.busy" @send="send" />
      <SlotChips v-if="view.slots.length" :slots="view.slots" />
      <p v-if="view.hint" class="echo">{{ view.hint }}</p>
      <HandoffBox v-if="view.handoff" :handoff="view.handoff" />
      <ContactForm v-if="view.contact" :saved="view.contact.saved" :busy="s.busy" @save="s.saveContact" />
      <PurchaseSheet v-if="s.sheetProduct" :key="s.sheetProduct.code" :product="s.sheetProduct" :sizes="s.sheetProduct.sizes"
        :default-size="view.default_size" :busy="s.busy" @buy="s.buy" @close="s.closeSheet()" />
      <button v-if="view.screen === 'service'" class="switch" type="button" @click="s.browseShop(true)">새 축구화 찾기</button>
      <button v-else-if="s.browsing" class="switch" type="button" @click="s.browseShop(false)">내 주문으로 돌아가기</button>
      <DiscussionList v-if="showDiscussion" :key="view.echo ?? ''" :lines="view.discussion" :hidden="view.hidden" />
    </div>
  </section>
</template>

<style scoped>
/* 질문 하나 + 입력창 하나. 뒤에는 축구장과 후보 3켤레가 깔리고, 결과가 나오면 질문 블록이 카드 아래로 내려간다 */
.stage { position: relative; border-radius: 28px; overflow: hidden; isolation: isolate; background: var(--bg); }
.pitch { position: absolute; inset: 0; width: 100%; height: 100%; z-index: -1; pointer-events: none; }
.pitch * { stroke: var(--pitch); fill: none; stroke-width: 1.5; }
/* 구장 사진 배경: 글자가 읽히도록 위에 반투명 막을 덮고, 구장이 바뀌면 부드럽게 넘어간다 */
.bg { position: absolute; inset: 0; z-index: -2; background-size: cover; background-position: center; }
.bg::after { content: ""; position: absolute; inset: 0; background: var(--photo-veil); }
.bg-enter-active, .bg-leave-active { transition: opacity .8s ease; }
.bg-enter-from, .bg-leave-to { opacity: 0; }
.stage.photo .pitch { opacity: .55; }

.shelf-wrap { padding: 28px 20px 24px; }
.count { font-family: var(--font-display); font-weight: 700; font-size: 13px; color: var(--muted); font-variant-numeric: tabular-nums; margin-bottom: 14px; }
.count b { color: var(--fg); font-size: 15px; }
.shelf {
  display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px;
  filter: blur(var(--blur, 0px)) saturate(var(--sat, 1)); opacity: var(--dim, 1);
  transition: filter .7s ease, opacity .7s ease;
}
.shelf.paused { filter: grayscale(1) blur(2px); opacity: .45; }

.ask { display: flex; flex-direction: column; align-items: center; gap: 14px; text-align: center; padding: 24px 16px 28px; }
.stage.collect { min-height: 440px; }
.stage.collect .ask {
  position: absolute; inset: 0; justify-content: safe center; overflow-y: auto;
  background: radial-gradient(ellipse at center, var(--veil) 35%, transparent 80%);
}
.stage.photo.collect .ask { background: radial-gradient(ellipse at center, var(--veil) 30%, transparent 75%); }
.echo { margin: 0; font-size: 13px; color: var(--muted); max-width: 600px; overflow-wrap: anywhere; }
.q { margin: 0; font-family: var(--font-display); font-weight: 700; letter-spacing: -.02em; line-height: 1.3; text-wrap: balance; max-width: 760px; font-size: clamp(22px, 3.4vw, 34px); }
.q.long { font-size: clamp(19px, 2.4vw, 24px); font-weight: 600; }

@media (max-width: 760px) {
  .shelf { grid-template-columns: none; grid-auto-flow: column; grid-auto-columns: 78%; overflow-x: auto; scroll-snap-type: x mandatory; }
  .shelf :deep(.card) { scroll-snap-align: start; }
  .shelf-wrap { padding: 20px 12px; }
  .stage.collect { min-height: 0; }
  .stage.collect .ask { position: static; background: none; overflow: visible; }
}
</style>
