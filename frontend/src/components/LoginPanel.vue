<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'

import { useSession } from '../stores/session'

const s = useSession()
const mode = ref<'login' | 'signup'>('login')
const userId = ref('')
const name = ref('')
const password = ref('')
const first = ref<HTMLInputElement | null>(null)
onMounted(() => first.value?.focus())

const demo = computed(() => s.catalog?.demo_accounts ?? [])
const canSubmit = computed(() => !!userId.value.trim() && !!password.value && (mode.value === 'login' || !!name.value.trim()))

async function swap(next: 'login' | 'signup') {
  mode.value = next
  s.loginError = null
  await nextTick()
  first.value?.focus()
}

function submit() {
  if (mode.value === 'login') s.login(userId.value, password.value)
  else s.signup(userId.value, name.value, password.value)
}
</script>

<template>
  <div class="tabs" role="tablist" aria-label="로그인 또는 회원가입">
    <button type="button" role="tab" :aria-selected="mode === 'login'" @click="swap('login')">로그인</button>
    <button type="button" role="tab" :aria-selected="mode === 'signup'" @click="swap('signup')">회원가입</button>
  </div>
  <p v-if="s.loginMessage">{{ s.loginMessage }}</p>

  <form class="fields" @submit.prevent="submit">
    <label>아이디
      <input ref="first" v-model="userId" type="text" name="username" maxlength="20" autocomplete="username" autocapitalize="none" spellcheck="false"
        :placeholder="mode === 'signup' ? '영문 소문자·숫자 3~20자' : ''" :aria-invalid="!!s.loginError" aria-describedby="login-err" />
    </label>
    <label v-if="mode === 'signup'">이름
      <input v-model="name" type="text" name="name" maxlength="20" autocomplete="name" />
    </label>
    <label>비밀번호
      <input v-model="password" type="password" name="password" maxlength="72" :autocomplete="mode === 'signup' ? 'new-password' : 'current-password'"
        :placeholder="mode === 'signup' ? '8자 이상' : ''" />
    </label>
    <button class="pill-btn dark" type="submit" :disabled="s.busy || !canSubmit">{{ mode === 'login' ? '로그인' : '가입하고 시작하기' }}</button>
  </form>
  <p id="login-err" class="err" role="alert">{{ s.loginError }}</p>

  <template v-if="demo.length && mode === 'login'">
    <p>데모 계정은 비밀번호 없이 아이디를 누르면 들어가요.</p>
    <table class="demo-ids">
      <caption class="sr-only">데모 계정</caption>
      <tbody>
        <tr v-for="a in demo" :key="a.id">
          <td><button class="id" type="button" :disabled="s.busy" @click="s.login(a.id)">{{ a.id }}</button></td>
          <td>{{ a.desc }}</td>
        </tr>
      </tbody>
    </table>
  </template>
</template>

<style scoped>
.tabs { display: flex; gap: 6px; }
.tabs button { background: none; border: 0; padding: 4px 2px; margin-right: 12px; font-family: var(--font-display); font-size: 17px; font-weight: 700; color: var(--muted); border-bottom: 2px solid transparent; }
.tabs button[aria-selected="true"] { color: var(--fg); border-bottom-color: var(--fg); }
.fields { display: flex; gap: 10px; flex-wrap: wrap; align-items: flex-end; }
label { flex: 1 1 180px; display: flex; flex-direction: column; gap: 4px; font-size: 12.5px; color: var(--muted); }
input { min-width: 0; border: 1px solid var(--line); border-radius: 12px; padding: 10px 14px; background: var(--bg); font-size: 16px; color: var(--fg); }
input[aria-invalid="true"] { border-color: var(--g-red); }
.fields .pill-btn { padding: 10px 18px; font-size: 14px; }
p.err.err { color: var(--g-red); }
.err:empty { display: none; }
.demo-ids { width: 100%; border-collapse: collapse; font-size: 13px; }
td { padding: 6px 4px; border-top: 1px solid var(--line); }
td:first-child { width: 96px; }
.id { background: none; border: 0; padding: 0; font-family: var(--font-display); font-weight: 700; text-decoration: underline; text-underline-offset: 3px; }
</style>
