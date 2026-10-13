<script setup lang="ts">
import { useSession } from '../stores/session'

const s = useSession()
</script>

<template>
  <header class="top">
    <div class="brand">
      <button class="wordmark" type="button" aria-label="PITCHROOM 첫 화면으로" :disabled="s.busy" @click="s.goHome()">PITCHROOM</button>
      <span class="tag">AI 축구화 상담 · 데모</span>
    </div>
    <nav class="who" aria-label="계정">
      <button v-if="!s.adminOpen && s.catalog" class="pill-btn" type="button" :aria-expanded="s.panel === 'catalog'" aria-controls="panel" @click="s.togglePanel('catalog')">전체 축구화 {{ s.catalog.products.length }}</button>
      <template v-if="s.account">
        <span class="me">{{ s.account.name }}님</span>
        <button v-if="s.isAdmin" class="pill-btn" :class="{ dark: !s.adminOpen }" type="button" @click="s.adminOpen = !s.adminOpen">{{ s.adminOpen ? '매장 화면' : '관리' }}</button>
        <button v-if="!s.isAdmin" class="pill-btn" type="button" :aria-expanded="s.panel === 'orders'" aria-controls="panel" @click="s.togglePanel('orders')">내 주문 {{ s.account.orders.length }}</button>
        <button class="pill-btn" type="button" :disabled="s.busy" @click="s.logout()">로그아웃</button>
      </template>
      <button v-else class="pill-btn dark" type="button" :aria-expanded="s.panel === 'login'" aria-controls="panel" @click="s.togglePanel('login')">로그인</button>
      <button v-if="!s.adminOpen" class="pill-btn quiet" type="button" :disabled="s.busy" @click="s.reset()">처음부터</button>
    </nav>
  </header>
</template>

<style scoped>
.top { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-block: 18px; }
.brand { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.wordmark { font-family: var(--font-display); font-weight: 800; letter-spacing: .14em; font-size: 15px; background: none; border: 0; padding: 4px 0; color: var(--fg); }
.wordmark:hover:not(:disabled) { opacity: .7; }
.wordmark:disabled { opacity: 1; }
.tag { font-size: 11.5px; color: var(--muted); border: 1px solid var(--line); border-radius: 999px; padding: 2px 9px; white-space: nowrap; }
.who { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.me { font-size: 13px; font-weight: 600; }
</style>
