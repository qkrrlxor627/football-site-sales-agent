<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'

import AdminView from './components/AdminView.vue'
import AppHeader from './components/AppHeader.vue'
import CatalogPanel from './components/CatalogPanel.vue'
import ErrorToast from './components/ErrorToast.vue'
import LoginPanel from './components/LoginPanel.vue'
import OrdersPanel from './components/OrdersPanel.vue'
import StageView from './components/StageView.vue'
import { useAdmin } from './stores/admin'
import { useSession } from './stores/session'

const s = useSession()
onMounted(s.init)
watch(() => s.isAdmin, (on) => !on && useAdmin().clear()) // 로그아웃하면 관리 데이터도 화면에서 지운다

const showLogin = computed(() => s.panel === 'login' && !s.account)
const showOrders = computed(() => s.panel === 'orders' && !!s.account)
const showCatalog = computed(() => s.panel === 'catalog' && !s.adminOpen)
const source = computed(() => s.view?.source ?? s.modeText)
</script>

<template>
  <div class="wrap">
    <AppHeader />

    <section v-if="showLogin || showOrders || showCatalog" id="panel" class="panel" :aria-label="showLogin ? '로그인' : showCatalog ? '전체 축구화' : '내 주문'" @keydown.esc="s.panel = null">
      <LoginPanel v-if="showLogin" />
      <CatalogPanel v-else-if="showCatalog" />
      <OrdersPanel v-else-if="s.account" :account="s.account" />
    </section>

    <main>
      <AdminView v-if="s.ready && s.isAdmin && s.adminOpen" />
      <StageView v-else-if="s.ready && s.view" :view="s.view" />
      <div v-else class="boot" :aria-busy="!s.fatal">
        <template v-if="s.fatal">
          <p role="alert">{{ s.fatal }}</p>
          <button class="pill-btn dark" type="button" @click="s.init()">다시 시도</button>
        </template>
        <p v-else>불러오는 중…</p>
      </div>
    </main>

    <p class="foot">
      데모입니다. 상품·가격·주문·정책은 시연용 예시예요. 문장 이해: <b>{{ source }}</b>. 판단은 항상 규칙이 하고, 고객 화면에는 공개 논의만 전달돼요.
    </p>
    <ErrorToast :message="s.error" @close="s.dismissError()" />
  </div>
</template>

<style scoped>
.wrap { max-width: 1040px; margin: 0 auto; padding-inline: 16px; padding-block: 0 32px; }
.panel { margin-bottom: 16px; border: 1px solid var(--line); background: var(--surface); border-radius: 20px; padding: 18px; display: flex; flex-direction: column; gap: 12px; animation: rise .25s ease both; }
.panel :deep(h2) { margin: 0; font-family: var(--font-display); font-size: 17px; }
.panel :deep(p) { margin: 0; font-size: 13.5px; color: var(--muted); }
.boot { min-height: 440px; border-radius: 28px; border: 1px solid var(--line); display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px; color: var(--muted); text-align: center; padding: 24px; }
.boot p { margin: 0; }
.foot { font-size: 12px; color: var(--muted); padding-top: 14px; margin: 0; }
</style>
