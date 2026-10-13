import { defineStore } from 'pinia'
import { ref } from 'vue'

import { api, ApiError } from '../api'
import type { AdminBoard } from '../types'

// 관리 화면 상태. 모든 변경 API가 최신 보드를 통째로 돌려주므로, 받은 것으로 갈아 끼우기만 한다.
export const useAdmin = defineStore('admin', () => {
  const board = ref<AdminBoard | null>(null)
  const busy = ref(false)
  const error = ref<string | null>(null)

  async function run(call: () => Promise<AdminBoard>, quiet = false) {
    if (busy.value) return false
    busy.value = true
    if (!quiet) error.value = null
    try {
      board.value = await call()
      error.value = null
      return true
    } catch (err) {
      if (!quiet || !board.value) error.value = err instanceof ApiError ? err.message : '알 수 없는 문제가 생겼어요.'
      return false
    } finally {
      busy.value = false
    }
  }

  return {
    board, busy, error,
    load: (quiet = false) => run(() => api.adminBoard(), quiet),
    setStatus: (orderId: string, to: string, note?: string, newSize?: number) => run(() => api.adminSetStatus(orderId, to, note, newSize)),
    updateProduct: (code: string, change: { price?: number; active?: boolean; stock?: Record<number, number> }) =>
      run(() => api.adminUpdateProduct(code, change)),
    /** 임시 비밀번호를 만들어 돌려준다 (화면에 한 번 보여주고 저장하지 않는다). 실패하면 null. */
    resetPassword: async (userId: string): Promise<string | null> => {
      error.value = null
      try {
        return (await api.adminResetPassword(userId)).temp_password
      } catch (err) {
        error.value = err instanceof ApiError ? err.message : '알 수 없는 문제가 생겼어요.'
        return null
      }
    },
    resolve: (handoffId: number, note: string) => run(() => api.adminResolve(handoffId, note)),
    clear: () => {
      board.value = null
      error.value = null
    },
  }
})
