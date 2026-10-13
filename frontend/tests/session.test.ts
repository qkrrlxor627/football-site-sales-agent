import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ProductCard from '../src/components/ProductCard.vue'
import { useSession } from '../src/stores/session'
import type { Account, Catalog, ProductCard as Card, View } from '../src/types'

const view = (over: Partial<View> = {}): View => ({
  screen: 'shop', headline: '어떤 구장에서 뛰세요?', echo: null, collect: true,
  count: { prefix: '전체 10종', strong: '', suffix: '' },
  shelf: { kind: 'products', blur: 12, paused: false, cards: [], empty_text: null },
  news: null, slots: [], handoff: null, hint: null, discussion: [], hidden: 0,
  route: null, reason: null, source: null, placeholder: '', default_size: 270, contact: null, background: null, ...over,
})
const card: Card = {
  code: 'S-08', name: 'Tiempo Maestro Pro', line: 'Tiempo', stud: 'AG', stud_info: '인조잔디용 짧고 많은 스터드', width: '넓음',
  price: 219000, list_price: null, color: '핑크', feel: '가죽 어퍼', image: null, label: '먼저 신어볼 1켤레', quiet: false, best: true, trade: null, why: '인조잔디 → AG', buyable: true, sizes: [265, 270], size_note: null,
}
const catalog: Catalog = {
  products: [{ ...card, surfaces: ['인조잔디'] }], surfaces: ['인조잔디'], lines: ['Tiempo'], demo_accounts: [{ id: 'jiwoo', name: '지우', desc: '배송 완료 3일째' }], policy: {}, shop_home: view(),
}
const jiwoo: Account = { id: 'jiwoo', name: '지우', role: 'customer', orders: [] }
const health = { ok: true, llm: false, model: null, search: false }

type Reply = { status?: number; body: unknown }
let routes: Record<string, Reply | (() => Reply)>
const calls: { url: string; body: unknown }[] = []

beforeEach(() => {
  setActivePinia(createPinia())
  calls.length = 0
  routes = {
    'GET /api/catalog': { body: catalog },
    'GET /api/health': { body: health },
    'GET /api/session': { body: { account: null, view: view() } },
  }
  vi.stubGlobal('fetch', async (url: string, init: RequestInit) => {
    const key = `${init.method} ${url}`
    calls.push({ url: key, body: init.body ? JSON.parse(init.body as string) : undefined })
    const hit = routes[key]
    if (!hit) throw new TypeError('network down')
    const { status = 200, body } = typeof hit === 'function' ? hit() : hit
    return new Response(JSON.stringify(body), { status })
  })
})

describe('session store', () => {
  it('loads catalog, session and mode on init', async () => {
    const s = useSession()
    await s.init()
    expect(s.ready).toBe(true)
    expect(s.view?.screen).toBe('shop')
    expect(s.modeText).toBe('키워드 규칙 (LLM 키 없음)')
  })

  it('shows a retryable fatal error when the server is down', async () => {
    routes = {}
    const s = useSession()
    await s.init()
    expect(s.ready).toBe(false)
    expect(s.fatal).toContain('서버에 연결하지 못했어요')
  })

  it('replaces the view with the server reply and ignores blank input', async () => {
    routes['POST /api/chat'] = { body: { account: null, view: view({ screen: 'result', headline: '발볼은 어떤 편이에요?', echo: '인조잔디' }) } }
    const s = useSession()
    await s.init()
    expect(await s.send('   ')).toBe(false)
    expect(await s.send(' 인조잔디 ')).toBe(true)
    expect(calls.at(-1)).toEqual({ url: 'POST /api/chat', body: { text: '인조잔디' } })
    expect(s.view?.headline).toBe('발볼은 어떤 편이에요?')
    expect(s.busy).toBe(false)
  })

  it('keeps the current view and raises a toast when a turn fails', async () => {
    routes['POST /api/chat'] = { status: 500, body: { error: { code: 'server_error', message: '서버에서 문제가 생겼어요.' } } }
    const s = useSession()
    await s.init()
    expect(await s.send('인조잔디')).toBe(false)
    expect(s.error).toBe('서버에서 문제가 생겼어요.')
    expect(s.view?.headline).toBe('어떤 구장에서 뛰세요?')
  })

  it('puts a failed login error inside the login panel, not in a toast', async () => {
    routes['POST /api/login'] = { status: 401, body: { error: { code: 'bad_credentials', message: '아이디 또는 비밀번호가 맞지 않아요.' } } }
    const s = useSession()
    await s.init()
    s.togglePanel('login')
    expect(await s.login('nobody', 'wrong-password')).toBe(false)
    expect(calls.at(-1)?.body).toEqual({ user_id: 'nobody', password: 'wrong-password', keep: false })
    expect(s.loginError).toBe('아이디 또는 비밀번호가 맞지 않아요.')
    expect(s.error).toBeNull()
    expect(s.panel).toBe('login')
  })

  it('asks for login before buying, then resumes the purchase in the same conversation', async () => {
    const recommend = view({ screen: 'result', route: 'recommend', collect: false })
    routes['POST /api/login'] = { body: { account: jiwoo, view: recommend } }
    routes['POST /api/orders'] = { body: { account: jiwoo, view: view({ screen: 'service', headline: '주문했어요. PR-0006' }), order_id: 'PR-0006' } }
    const s = useSession()
    await s.init()

    s.requestBuy('S-08')
    expect(s.panel).toBe('login')
    expect(s.sheetCode).toBeNull()

    await s.login('jiwoo')
    expect(calls.at(-1)?.body).toEqual({ user_id: 'jiwoo', keep: true })
    expect(s.panel).toBeNull()
    expect(s.sheetProduct?.code).toBe('S-08')

    expect(await s.buy(270)).toBe(true)
    expect(calls.find((c) => c.url === 'POST /api/orders')?.body).toEqual({ code: 'S-08', size: 270 })
    expect(calls.at(-1)?.url).toBe('GET /api/catalog') // 재고가 줄었으니 다시 받는다
    expect(s.sheetCode).toBeNull()
    expect(s.panel).toBe('orders')
    expect(s.view?.headline).toContain('PR-0006')
  })

  it('signs up and lands logged in; a taken id is reported in the panel', async () => {
    routes['POST /api/signup'] = { status: 409, body: { error: { code: 'id_taken', message: '이미 쓰고 있는 아이디예요.' } } }
    const s = useSession()
    await s.init()
    s.togglePanel('login')
    expect(await s.signup('jiwoo', '지우', 'correct-horse')).toBe(false)
    expect(s.loginError).toBe('이미 쓰고 있는 아이디예요.')
    routes['POST /api/signup'] = { body: { account: { ...jiwoo, id: 'taeho', name: '태호' }, view: view() } }
    expect(await s.signup('taeho', '태호', 'correct-horse')).toBe(true)
    expect(s.account?.name).toBe('태호')
    expect(s.panel).toBeNull()
    expect(s.adminOpen).toBe(false)
  })

  it('opens the admin screen for an admin and closes it on logout', async () => {
    routes['POST /api/login'] = { body: { account: { id: 'admin', name: '사장님', role: 'admin', orders: [] }, view: view() } }
    routes['POST /api/logout'] = { body: { account: null, view: view() } }
    const s = useSession()
    await s.init()
    await s.login('admin', 'test-admin-pw')
    expect(s.isAdmin).toBe(true)
    expect(s.adminOpen).toBe(true)
    await s.logout()
    expect(s.adminOpen).toBe(false)
  })

  it('goes home from the wordmark: new conversation, panels closed, still logged in', async () => {
    routes['GET /api/session'] = { body: { account: jiwoo, view: view({ screen: 'result', headline: '추천 결과' }) } }
    routes['POST /api/reset'] = { body: { account: jiwoo, view: view({ screen: 'service', headline: '지우님, 무엇을 도와드릴까요?' }) } }
    const s = useSession()
    await s.init()
    s.togglePanel('catalog')
    s.requestBuy('S-08')
    expect(await s.goHome()).toBe(true)
    expect(calls.at(-1)?.url).toBe('POST /api/reset')
    expect(s.account?.id).toBe('jiwoo')
    expect(s.view?.screen).toBe('service')
    expect(s.panel).toBeNull()
    expect(s.sheetCode).toBeNull()
  })

  it('takes an admin from the admin screen back to the shop home', async () => {
    const admin = { id: 'admin', name: '사장', role: 'admin' as const, orders: [] }
    routes['GET /api/session'] = { body: { account: admin, view: view() } }
    routes['POST /api/reset'] = { body: { account: admin, view: view() } }
    const s = useSession()
    await s.init()
    expect(s.adminOpen).toBe(true)
    await s.goHome()
    expect(s.adminOpen).toBe(false)
    expect(s.isAdmin).toBe(true)
  })

  it('lets a customer with orders browse the shop and come back', async () => {
    routes['GET /api/session'] = { body: { account: jiwoo, view: view({ screen: 'service', headline: '지우님' }) } }
    const s = useSession()
    await s.init()
    s.browseShop(true)
    expect(s.view?.screen).toBe('shop')
    s.browseShop(false)
    expect(s.view?.screen).toBe('service')
  })
})

describe('ProductCard', () => {
  it('shows the label, price and a buy button, and falls back when there is no photo', async () => {
    const w = mount(ProductCard, { props: { card } })
    expect(w.text()).toContain('먼저 신어볼 1켤레')
    expect(w.text()).toContain('219,000원')
    expect(w.find('img').exists()).toBe(false)
    expect(w.find('.no-photo').text()).toBe('AG')
    await w.find('button.buy').trigger('click')
    expect(w.emitted('buy')).toEqual([['S-08']])
  })

  it('shows the discount against the list price', () => {
    const w = mount(ProductCard, { props: { card: { ...card, price: 146000, list_price: 224000 } } })
    expect(w.find('.off').text()).toBe('35%')
    expect(w.find('s').text()).toContain('224,000원')
  })

  it('marks a sold-out shoe and blocks buying it', () => {
    const w = mount(ProductCard, { props: { card: { ...card, sizes: [], size_note: '전 사이즈 품절' } } })
    expect(w.text()).toContain('전 사이즈 품절')
    expect(w.find('button.buy').attributes('disabled')).toBeDefined()
    expect(w.find('button.buy').text()).toBe('품절')
  })

  it('lists trade-offs instead of the reason when the shoe is a compromise', () => {
    const w = mount(ProductCard, { props: { card: { ...card, trade: ['발볼 보통 (매장 시착 권장)'], buyable: false } } })
    expect(w.text()).toContain('발볼 보통 (매장 시착 권장)')
    expect(w.text()).not.toContain('인조잔디 → AG')
    expect(w.find('button.buy').exists()).toBe(false)
  })
})
