import type { AdminBoard, Catalog, Envelope, Health } from './types'

// 서버 오류는 항상 { error: { code, message } } 모양으로 온다. 연결 실패·시간 초과도 같은 모양으로 맞춘다.
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

const TIMEOUT_MS = 30_000

async function request<T>(method: 'GET' | 'POST', path: string, body?: unknown): Promise<T> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS)
  let res: Response
  try {
    res = await fetch(path, {
      method,
      credentials: 'same-origin',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: ctrl.signal,
    })
  } catch {
    throw ctrl.signal.aborted
      ? new ApiError(0, 'timeout', '응답이 너무 늦어요. 잠시 뒤 다시 시도해 주세요.')
      : new ApiError(0, 'network', '서버에 연결하지 못했어요. 서버가 켜져 있는지 확인해 주세요.')
  } finally {
    clearTimeout(timer)
  }
  const data = await res.json().catch(() => null)
  if (!res.ok || data === null) {
    throw new ApiError(res.status, data?.error?.code ?? 'http_error', data?.error?.message ?? '요청을 처리하지 못했어요. 잠시 뒤 다시 시도해 주세요.')
  }
  return data as T
}

export const api = {
  health: () => request<Health>('GET', '/api/health'),
  catalog: () => request<Catalog>('GET', '/api/catalog'),
  session: () => request<Envelope>('GET', '/api/session'),
  chat: (text: string) => request<Envelope>('POST', '/api/chat', { text }),
  login: (user_id: string, password: string | undefined, keep = false) => request<Envelope>('POST', '/api/login', { user_id, password, keep }),
  signup: (user_id: string, name: string, password: string, keep = false) => request<Envelope>('POST', '/api/signup', { user_id, name, password, keep }),
  logout: () => request<Envelope>('POST', '/api/logout'),
  reset: () => request<Envelope>('POST', '/api/reset'),
  order: (code: string, size: number) => request<Envelope>('POST', '/api/orders', { code, size }),
  adminBoard: () => request<AdminBoard>('GET', '/api/admin/board'),
  adminSetStatus: (orderId: string, to: string, note?: string) =>
    request<AdminBoard>('POST', `/api/admin/orders/${encodeURIComponent(orderId)}/status`, { to, note: note || undefined }),
  adminResolve: (handoffId: number, note: string) => request<AdminBoard>('POST', `/api/admin/handoffs/${handoffId}/resolve`, { note }),
}
