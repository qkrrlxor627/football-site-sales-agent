import type { News } from './types'

// 접수 메모: 고객이 내려받아 보관하는 한 장. 고객 화면에 이미 보인 내용만 담는다 (내부 논의는 서버에서 오지 않는다).

export interface MemoBlock {
  kind: 'title' | 'label' | 'text' | 'bullet' | 'stamp' | 'rule' | 'small'
  text: string
}

/** 메모에 들어갈 내용을 순서대로. 화면의 메모지, 이미지, 복사용 글이 모두 이 목록 하나에서 나온다. */
export function memoBlocks(news: News, echo: string | null): MemoBlock[] {
  const out: MemoBlock[] = [
    { kind: 'title', text: 'PITCHROOM 접수 메모' },
    { kind: 'small', text: news.date },
    { kind: 'stamp', text: news.verdict },
    { kind: 'label', text: '문의' },
    { kind: 'text', text: news.summary },
  ]
  if (echo) out.push({ kind: 'label', text: '고객 말씀' }, { kind: 'text', text: `“${echo}”` })
  if (news.rules.length) out.push({ kind: 'label', text: '적용한 규칙' }, ...news.rules.map((text) => ({ kind: 'bullet' as const, text })))
  out.push({ kind: 'label', text: '결론' }, { kind: 'text', text: news.next })
  if (news.options.length) out.push({ kind: 'label', text: '선택할 수 있는 방법' }, ...news.options.map((text) => ({ kind: 'bullet' as const, text })))
  out.push({ kind: 'rule', text: '' }, { kind: 'small', text: '이 메모는 상담 화면에 표시된 내용을 그대로 옮긴 것이에요.' })
  return out
}

export function memoText(news: News, echo: string | null): string {
  return memoBlocks(news, echo)
    .map((b) => {
      if (b.kind === 'title') return b.text
      if (b.kind === 'stamp') return `[${b.text}]`
      if (b.kind === 'label') return `\n■ ${b.text}`
      if (b.kind === 'bullet') return `- ${b.text}`
      if (b.kind === 'rule') return '\n----------'
      return b.text
    })
    .join('\n')
}

/** 파일 이름: 주문 번호가 있으면 넣는다. 예: pitchroom-메모-PR-0005-2026-10-13.png */
export function memoFileName(news: News, ext: 'png' | 'jpg'): string {
  const order = news.summary.match(/PR-\d+/)?.[0]
  return ['pitchroom-메모', order, news.date].filter(Boolean).join('-') + `.${ext}`
}

/** 글을 주어진 폭에 맞게 줄바꿈한다. 한글은 띄어쓰기 없이도 글자 단위로 끊는다. */
export function wrapText(text: string, maxWidth: number, measure: (s: string) => number): string[] {
  const lines: string[] = []
  let line = ''
  for (const word of text.split(/(\s+)/)) {
    if (measure(line + word) <= maxWidth) {
      line += word
      continue
    }
    if (line.trim()) lines.push(line.trimEnd())
    line = ''
    let rest = word.trimStart()
    while (measure(rest) > maxWidth) {
      // 한 단어가 한 줄보다 길면 글자 단위로 자른다
      let cut = rest.length - 1
      while (cut > 1 && measure(rest.slice(0, cut)) > maxWidth) cut--
      lines.push(rest.slice(0, cut))
      rest = rest.slice(cut)
    }
    line = rest
  }
  if (line.trim()) lines.push(line.trimEnd())
  return lines.length ? lines : ['']
}

const PAPER = '#fff8dc'
const INK = '#2b2620'
const MUTED = '#8a7f6a'
const FONT = '"Noto Sans KR", "Apple SD Gothic Neo", system-ui, sans-serif'
const STYLE = {
  title: { size: 26, weight: 800, color: INK, gapBefore: 0, lineHeight: 1.3 },
  small: { size: 14, weight: 400, color: MUTED, gapBefore: 4, lineHeight: 1.5 },
  label: { size: 14, weight: 700, color: MUTED, gapBefore: 22, lineHeight: 1.5 },
  text: { size: 18, weight: 500, color: INK, gapBefore: 4, lineHeight: 1.55 },
  bullet: { size: 17, weight: 400, color: INK, gapBefore: 4, lineHeight: 1.55 },
} as const

/** 메모지를 그림으로 그린다. 외부 라이브러리 없이 캔버스에 직접 써서, 화면 스타일이나 보안 정책에 영향받지 않는다. */
export async function drawMemo(news: News, echo: string | null, hold: boolean): Promise<HTMLCanvasElement> {
  await document.fonts?.ready
  const W = 720
  const PAD = 44
  const SCALE = 2
  const inner = W - PAD * 2
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('canvas')
  const font = (s: { size: number; weight: number }) => `${s.weight} ${s.size}px ${FONT}`

  // 1) 먼저 줄바꿈과 높이를 계산하고
  type Op = { y: number; draw: (c: CanvasRenderingContext2D) => void }
  const ops: Op[] = []
  let y = PAD + 8
  for (const b of memoBlocks(news, echo)) {
    if (b.kind === 'rule') {
      y += 22
      const at = y
      ops.push({ y: at, draw: (c) => { c.strokeStyle = '#d9cfae'; c.setLineDash([6, 6]); c.beginPath(); c.moveTo(PAD, at); c.lineTo(W - PAD, at); c.stroke(); c.setLineDash([]) } })
      y += 10
      continue
    }
    if (b.kind === 'stamp') {
      y += 16
      const at = y
      const color = hold ? '#b06000' : '#188038'
      ops.push({ y: at, draw: (c) => {
        c.font = `700 16px ${FONT}`
        const w = c.measureText(b.text).width + 28
        c.strokeStyle = color; c.lineWidth = 2
        c.beginPath(); c.roundRect(PAD, at, w, 34, 17); c.stroke()
        c.fillStyle = color; c.textBaseline = 'middle'; c.fillText(b.text, PAD + 14, at + 18); c.textBaseline = 'alphabetic'
      } })
      y += 34
      continue
    }
    const s = STYLE[b.kind]
    ctx.font = font(s)
    const indent = b.kind === 'bullet' ? 18 : 0
    const lines = wrapText(b.text, inner - indent, (t) => ctx.measureText(t).width)
    y += s.gapBefore
    lines.forEach((text, i) => {
      y += s.size * s.lineHeight
      const at = y
      ops.push({ y: at, draw: (c) => {
        c.font = font(s); c.fillStyle = s.color
        if (indent && i === 0) c.fillText('•', PAD + 2, at)
        c.fillText(text, PAD + indent, at)
      } })
    })
  }
  const H = Math.ceil(y + PAD)

  // 2) 크기를 정한 뒤 그린다
  canvas.width = W * SCALE
  canvas.height = H * SCALE
  ctx.scale(SCALE, SCALE)
  ctx.fillStyle = PAPER
  ctx.fillRect(0, 0, W, H)
  ctx.fillStyle = '#f3e7b3' // 위쪽 접착 띠
  ctx.fillRect(0, 0, W, 14)
  for (const op of ops) op.draw(ctx)
  return canvas
}

export async function downloadMemo(news: News, echo: string | null, format: 'png' | 'jpg'): Promise<void> {
  const canvas = await drawMemo(news, echo, news.hold)
  const blob = await new Promise<Blob | null>((done) => canvas.toBlob(done, format === 'png' ? 'image/png' : 'image/jpeg', 0.92))
  if (!blob) throw new Error('이미지를 만들지 못했어요.')
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = memoFileName(news, format)
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
