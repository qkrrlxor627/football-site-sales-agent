<script setup lang="ts">
import { useSession } from '../stores/session'

const s = useSession()
</script>

<template>
  <header class="top">
    <div class="brand"><span class="wordmark">PITCHROOM</span><span class="tag">AI 축구화 상담 · 데모</span></div>
    <nav class="who" aria-label="계정">
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
.wordmark { font-family: var(--font-display); font-weight: 800; letter-spacing: .14em; font-size: 15px; }
.tag { font-size: 11.5px; color: var(--muted); border: 1px solid var(--line); border-radius: 999px; padding: 2px 9px; white-space: nowrap; }
.who { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.me { font-size: 13px; font-weight: 600; }
</style>
