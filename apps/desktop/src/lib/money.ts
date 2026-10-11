import type { ResultMsg } from '../bridge/protocol'
import { t } from './i18n'

/** 小额多给一位，和账本（¥0.0161）对得上 */
export function fmtCny(v: number): string {
  return v < 0.1 ? v.toFixed(4) : v.toFixed(3)
}

/** 悬停：实付与名义价不同（命中本地缓存）时说明差额 */
export function costTitle(r: Pick<ResultMsg, 'cost_cny' | 'nominal_cost_cny'>): string {
  const n = r.nominal_cost_cny
  if (n === undefined || Math.abs(n - r.cost_cny) < 1e-6) return t('实付 ¥{0}（与账本一致）', fmtCny(r.cost_cny))
  return t('实付 ¥{0}（与账本一致）；名义价 ¥{1}，差额来自本地缓存命中，未计费', fmtCny(r.cost_cny), fmtCny(n))
}
