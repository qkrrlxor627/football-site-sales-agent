// 서버(pitchroom/views.py)가 내려주는 화면 JSON의 모양. 화면은 이 타입에 있는 것만 안다.

export interface Product {
  code: string
  name: string
  line: string
  stud: string
  stud_info: string
  width: string
  price: number
  feel: string
  image: string | null
}

/** 카탈로그의 상품: 재고가 있는 사이즈를 함께 준다 */
export interface CatalogProduct extends Product {
  sizes: number[]
}

export interface ProductCard extends Product {
  label: string | null
  quiet: boolean
  best: boolean
  trade: string[] | null
  why: string
  buyable: boolean
  sizes: number[] // 재고가 있는 사이즈
  size_note: string | null // 원하는 사이즈가 없을 때 (예: 270mm 품절)
}

export interface Step {
  text: string
  state: 'done' | 'now' | 'todo' | 'svc'
}

export interface OrderCard {
  id: string
  code: string
  name: string
  stud: string
  size: number
  label: string
  image: string | null
  status: string
  steps: Step[]
  when: string
  exchanges: number
  note: string | null
  primary: boolean
}

export interface Slot {
  key: string
  label: string
  text: string
  on: boolean
}

export interface Line {
  agent: string
  text: string
}

export interface News {
  summary: string
  rules: string[]
  verdict: string
  hold: boolean
  next: string
  options: string[]
  discussion: Line[]
  hidden: number
}

export interface Handoff {
  title: string
  body: string
  items: string[]
}

interface ShelfBase {
  blur: number
  paused: boolean
  empty_text: string | null
}

export type Shelf =
  | (ShelfBase & { kind: 'products'; cards: ProductCard[] })
  | (ShelfBase & { kind: 'orders'; cards: OrderCard[] })
  | (ShelfBase & { kind: 'news'; cards: [] })

export interface View {
  screen: 'shop' | 'service' | 'result'
  headline: string
  echo: string | null
  collect: boolean
  count: { prefix: string; strong: string; suffix: string }
  shelf: Shelf
  news: News | null
  slots: Slot[]
  handoff: Handoff | null
  hint: string | null
  discussion: Line[]
  hidden: number
  route: string | null
  reason: string | null
  source: string | null
  placeholder: string
  default_size: number
  contact: { saved: string | null } | null // 사람이 이어받는 건이면 연락받을 곳을 묻는다
}

export interface Account {
  id: string
  name: string
  role: 'customer' | 'admin'
  orders: OrderCard[]
}

export interface Envelope {
  account: Account | null
  view: View
  order_id?: string
}

export interface Catalog {
  products: CatalogProduct[]
  demo_accounts: { id: string; name: string; desc: string }[]
  policy: Record<string, string | number>
  shop_home: View
}

export interface Health {
  ok: boolean
  llm: boolean
  model: string | null
  search: boolean
}

// ---------- 관리 화면 ----------
export interface AdminOrder {
  id: string
  account_id: string
  account_name: string | null
  title: string
  status: string
  note: string | null
  exchanges: number
  code: string
  size: number
  ordered_at: string
  shipped_at: string | null
  delivered_at: string | null
  actions: { to: string; label: string; needs_size: boolean }[]
}

export interface AdminProduct {
  code: string
  name: string
  stud: string
  width: string
  price: number
  active: boolean
  stock: { size: number; qty: number }[]
}

export interface AdminCustomer {
  id: string
  name: string
  contact: string | null
  created_at: string | null
  has_password: boolean
  orders: number
}

export interface AdminHandoff {
  id: number
  created_at: string
  kind: string
  kind_label: string
  account_id: string | null
  account_name: string | null
  order_id: string | null
  contact: string | null
  summary: string
  status: 'open' | 'done'
  resolved_at: string | null
  resolution: string | null
  detail: {
    text: string
    reply: string | null
    source: string | null
    conditions: string[]
    rules: string[]
    options: string[]
    order: string | null
    discussion: { agent: string; text: string; internal: boolean }[]
  }
}

export interface AdminBoard {
  summary: { open_handoffs: number; to_ship: number; shipping: number; in_service: number; orders: number; customers: number }
  handoffs: AdminHandoff[]
  done: AdminHandoff[]
  orders: AdminOrder[]
  products: AdminProduct[]
  customers: AdminCustomer[]
}
