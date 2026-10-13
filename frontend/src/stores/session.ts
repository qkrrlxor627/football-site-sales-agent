import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { api, ApiError } from '../api'
import type { Account, Catalog, Envelope, Health, View } from '../types'

export type Panel = 'login' | 'orders' | null

// 화면 상태는 여기 한 곳에 둔다. 판단은 전부 서버가 하고, 여기서는 받은 화면을 들고 있다가 보여줄 뿐이다.
export const useSession = defineStore('session', () => {
  const catalog = ref<Catalog | null>(null)
  const health = ref<Health | null>(null)
  const account = ref<Account | null>(null)
  const serverView = ref<View | null>(null)

  const ready = ref(false)
  const fatal = ref<string | null>(null) // 첫 로딩 실패 (화면을 그릴 수 없음)
  const busy = ref(false)
  const error = ref<string | null>(null) // 그 뒤의 실패 (토스트)

  const panel = ref<Panel>(null)
  const loginMessage = ref<string | null>(null)
  const loginError = ref<string | null>(null)
  const sheetCode = ref<string | null>(null) // 구매 시트가 열려 있는 상품
  const pendingBuy = ref<string | null>(null) // 로그인 뒤 이어서 살 상품
  const browsing = ref(false) // 주문 화면에서 '새 축구화 찾기'를 누른 상태
  const adminOpen = ref(false) // 관리 화면을 보고 있는 상태 (관리자만)

  const view = computed<View | null>(() => (browsing.value && catalog.value ? catalog.value.shop_home : serverView.value))
  const isAdmin = computed(() => account.value?.role === 'admin')
  const sheetProduct = computed(() => catalog.value?.products.find((p) => p.code === sheetCode.value) ?? null)
  const modeText = computed(() => {
    if (!health.value) return '확인 중'
    return health.value.llm ? `LLM (${health.value.model})` : '키워드 규칙 (LLM 키 없음)'
  })

  function apply(res: Envelope) {
    account.value = res.account
    serverView.value = res.view
    browsing.value = false
  }

  function message(err: unknown) {
    return err instanceof ApiError ? err.message : '알 수 없는 문제가 생겼어요. 잠시 뒤 다시 시도해 주세요.'
  }

  /** 요청 하나를 돌린다. 겹친 요청은 무시하고, 실패는 토스트로 알린다. 성공하면 true. */
  async function run(call: () => Promise<Envelope>, onError?: (err: unknown) => boolean): Promise<boolean> {
    if (busy.value) return false
    busy.value = true
    error.value = null
    try {
      apply(await call())
      return true
    } catch (err) {
      if (!onError?.(err)) error.value = message(err)
      return false
    } finally {
      busy.value = false
    }
  }

  async function init() {
    fatal.value = null
    ready.value = false
    try {
      const [cat, sess, hp] = await Promise.all([api.catalog(), api.session(), api.health()])
      catalog.value = cat
      health.value = hp
      apply(sess)
      adminOpen.value = isAdmin.value
      ready.value = true
    } catch (err) {
      fatal.value = message(err)
    }
  }

  async function send(text: string) {
    const t = text.trim()
    if (!t) return false
    sheetCode.value = null
    return run(() => api.chat(t))
  }

  const AUTH_ERRORS = ['bad_credentials', 'invalid_input', 'rate_limited', 'id_taken']

  /** 로그인·가입 공통: 실패 이유는 토스트가 아니라 패널 안에 보여준다. 성공하면 하려던 구매를 이어 간다. */
  async function enter(call: (keep: boolean) => Promise<Envelope>) {
    loginError.value = null
    const keep = pendingBuy.value !== null // 추천을 보고 사려던 중이면 그 대화를 유지한다
    const ok = await run(
      () => call(keep),
      (err) => {
        if (err instanceof ApiError && AUTH_ERRORS.includes(err.code)) {
          loginError.value = err.message
          return true
        }
        return false
      },
    )
    if (!ok) return false
    panel.value = null
    loginMessage.value = null
    sheetCode.value = pendingBuy.value
    pendingBuy.value = null
    adminOpen.value = isAdmin.value // 사장님은 들어오면 바로 관리 화면
    return true
  }

  const login = (userId: string, password?: string) => enter((keep) => api.login(userId, password || undefined, keep))
  const signup = (userId: string, name: string, password: string) => enter((keep) => api.signup(userId, name, password, keep))

  function closeAll() {
    panel.value = null
    sheetCode.value = null
    pendingBuy.value = null
    loginMessage.value = null
    loginError.value = null
    if (!isAdmin.value) adminOpen.value = false
  }

  async function logout() {
    if (await run(() => api.logout())) closeAll()
  }

  async function reset() {
    if (await run(() => api.reset())) closeAll()
  }

  function requestBuy(code: string) {
    if (!account.value) {
      pendingBuy.value = code
      loginMessage.value = '구매하려면 로그인해 주세요.'
      loginError.value = null
      panel.value = 'login'
      return
    }
    sheetCode.value = code
  }

  async function buy(size: number) {
    const code = sheetCode.value
    if (!code) return false
    const ok = await run(
      () => api.order(code, size),
      (err) => {
        if (err instanceof ApiError && err.code === 'login_required') {
          account.value = null
          requestBuy(code)
          return true
        }
        return false
      },
    )
    if (ok) {
      sheetCode.value = null
      panel.value = 'orders'
    }
    return ok
  }

  function togglePanel(next: Exclude<Panel, null>) {
    panel.value = panel.value === next ? null : next
    if (panel.value !== 'login') {
      pendingBuy.value = null
      loginMessage.value = null
      loginError.value = null
    }
  }

  function browseShop(on: boolean) {
    browsing.value = on
    sheetCode.value = null
  }

  return {
    catalog, health, account, view, ready, fatal, busy, error, panel, loginMessage, loginError, sheetCode, sheetProduct,
    pendingBuy, browsing, modeText, isAdmin, adminOpen,
    init, send, login, signup, logout, reset, requestBuy, buy, togglePanel, browseShop,
    closeSheet: () => (sheetCode.value = null),
    dismissError: () => (error.value = null),
  }
})
