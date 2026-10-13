import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import CsNews from '../src/components/CsNews.vue'
import { memoFileName, memoText, wrapText } from '../src/memo'
import type { News } from '../src/types'

const news: News = {
  summary: '반품님 · PR-0005 · 반품 요청', rules: ['수령 후 7일 이내 ✓ 3일째', '실외 미착용 ✓'], verdict: '자동 접수', hold: false,
  next: '반품 접수 완료. 검수 후 왕복 배송비 6,000원을 뺀 금액이 환불돼요.', options: [],
  discussion: [{ agent: '정책 에이전트', text: '조건을 모두 충족해서 자동 접수할게요.' }, { agent: '접수 에이전트', text: 'PR-0005 주문을 "반품 접수" 상태로 바꿨어요.' }],
  hidden: 1, date: '2026-10-13',
}

describe('접수 메모', () => {
  it('puts the inquiry, rules and conclusion in the copied text, in order', () => {
    const text = memoText(news, '안 신었어요')
    expect(text.startsWith('PITCHROOM 접수 메모\n2026-10-13\n[자동 접수]')).toBe(true)
    expect(text).toContain('■ 문의\n반품님 · PR-0005 · 반품 요청')
    expect(text).toContain('■ 고객 말씀\n“안 신었어요”')
    expect(text).toContain('■ 적용한 규칙\n- 수령 후 7일 이내 ✓ 3일째\n- 실외 미착용 ✓')
    expect(text.indexOf('■ 결론')).toBeGreaterThan(text.indexOf('■ 적용한 규칙'))
    expect(text).not.toContain('선택할 수 있는 방법')
  })

  it('lists the options when the owner has to decide, and never carries agent discussion', () => {
    const text = memoText({ ...news, hold: true, verdict: '사장님 확인', options: ['예외 반품 요청', '같은 가격대 다른 모델로 교환'] }, null)
    expect(text).toContain('■ 선택할 수 있는 방법\n- 예외 반품 요청\n- 같은 가격대 다른 모델로 교환')
    expect(text).not.toContain('고객 말씀')
    expect(text).not.toContain('에이전트')
  })

  it('names the file after the order and date', () => {
    expect(memoFileName(news, 'png')).toBe('pitchroom-메모-PR-0005-2026-10-13.png')
    expect(memoFileName({ ...news, summary: '배송 문의' }, 'jpg')).toBe('pitchroom-메모-2026-10-13.jpg')
  })

  it('wraps on spaces and breaks a long unspaced run by character', () => {
    const measure = (s: string) => s.length * 10
    expect(wrapText('반품 접수 완료. 검수 후 환불돼요.', 100, measure)).toEqual(['반품 접수 완료.', '검수 후 환불돼요.'])
    expect(wrapText('가나다라마바사아자차카타파하', 50, measure)).toEqual(['가나다라마', '바사아자차', '카타파하'])
    expect(wrapText('', 50, measure)).toEqual([''])
  })
})

describe('CsNews', () => {
  it('shows the discussion as a chat with the customer first, and the conclusion as a memo', () => {
    const w = mount(CsNews, { props: { news, echo: '안 신었어요' } })
    const rows = w.findAll('.chat .row')
    expect(rows[0].classes()).toContain('me')
    expect(rows[0].text()).toBe('안 신었어요')
    expect(rows[1].find('.who').text()).toBe('정책 에이전트')
    expect(rows[1].find('.avatar').text()).toBe('정')
    expect(w.find('.chat .locked').text()).toContain('내부 논의 1건')
    expect(w.find('.memo .stamp').text()).toBe('자동 접수')
    expect(w.find('.memo').text()).toContain('반품 접수 완료')
    expect(w.findAll('.actions button').map((b) => b.text())).toEqual(['PNG로 저장', 'JPG로 저장', '내용 복사'])
  })

  it('copies the memo text to the clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    const w = mount(CsNews, { props: { news, echo: null } })
    await w.findAll('.actions button')[2].trigger('click')
    await Promise.resolve()
    expect(writeText).toHaveBeenCalledWith(memoText(news, null))
    await w.vm.$nextTick()
    expect(w.find('.status').text()).toBe('메모 내용을 복사했어요.')
  })
})
