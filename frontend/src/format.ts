export const won = (n: number) => `${n.toLocaleString('ko-KR')}원`

/** 정가 대비 할인율 (%). 예: 224,000 → 146,000 = 35 */
export const discount = (price: number, list: number) => Math.round((1 - price / list) * 100)
