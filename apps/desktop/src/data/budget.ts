import { t } from '../lib/i18n'
// 价格：DeepSeek 官方价目表（2026-10-10 核对），元 / 百万 token
// https://api-docs.deepseek.com/zh-cn/quick_start/pricing
export const PRICE = {
  idle: { hit: 0.02, miss: 1, out: 4 },
  peak: { hit: 0.04, miss: 2, out: 8 },
} as const

export const BUDGET_TOTAL = 100
export const TASK_CAP = 0.8

/** 北京时间工作日高峰（左闭右开，单位：小时） */
export const PEAK_WINDOWS: [number, number][] = [
  [9, 12],
  [14, 18],
]

export interface LedgerRow {
  id: string
  when: string
  task: string
  mode: '非思考' | '思考' // i18n-ignore: 键，显示时翻
  window: 'idle' | 'peak'
  hitM: number
  missM: number
  outM: number
}

export function rowCost(r: LedgerRow) {
  const p = PRICE[r.window]
  return r.hitM * p.hit + r.missM * p.miss + r.outM * p.out
}

export const ledger: LedgerRow[] = [
  { id: 'r1', when: '10-10 03:58', task: t('Issue #87 · 执行'), mode: '非思考', window: 'idle', hitM: 2.31, missM: 0.062, outM: 0.014 }, // i18n-ignore: 键，显示时翻
  { id: 'r2', when: '10-10 04:06', task: t('Issue #87 · 评审'), mode: '思考', window: 'idle', hitM: 0.84, missM: 0.031, outM: 0.009 }, // i18n-ignore: 键，显示时翻
  { id: 'r3', when: '10-09 22:41', task: 'dev suite · task-03', mode: '非思考', window: 'idle', hitM: 3.12, missM: 0.088, outM: 0.021 }, // i18n-ignore: 键，显示时翻
  { id: 'r4', when: '10-09 22:17', task: 'dev suite · task-02', mode: '非思考', window: 'idle', hitM: 2.64, missM: 0.071, outM: 0.017 }, // i18n-ignore: 键，显示时翻
  { id: 'r5', when: '10-09 21:50', task: 'dev suite · task-01', mode: '非思考', window: 'idle', hitM: 1.97, missM: 0.054, outM: 0.012 }, // i18n-ignore: 键，显示时翻
  { id: 'r6', when: '10-08 19:12', task: t('适配层冒烟测试'), mode: '思考', window: 'idle', hitM: 0.22, missM: 0.019, outM: 0.006 }, // i18n-ignore: 键，显示时翻
]

/** 以北京时间（UTC+8）解释“现在”，与本机时区无关 */
export function beijingNow(d = new Date()) {
  const bj = new Date(d.getTime() + 8 * 3600_000)
  const day = bj.getUTCDay() // 0 = 周日
  const minutes = bj.getUTCHours() * 60 + bj.getUTCMinutes()
  return { day, minutes, hh: bj.getUTCHours(), mm: bj.getUTCMinutes() }
}

export function gateStatus(d = new Date()) {
  const { day, minutes } = beijingNow(d)
  const weekday = day >= 1 && day <= 5
  const inPeak = weekday && PEAK_WINDOWS.some(([a, b]) => minutes >= a * 60 && minutes < b * 60)
  // 下一次切换
  const pad = (h: number) => `${String(h).padStart(2, '0')}:00`
  let nextShort: string
  let next: string
  if (inPeak) {
    const w = PEAK_WINDOWS.find(([a, b]) => minutes >= a * 60 && minutes < b * 60)!
    nextShort = pad(w[1])
    next = t('{0} 转空闲', pad(w[1]))
  } else if (weekday) {
    const w = PEAK_WINDOWS.find(([a]) => minutes < a * 60)
    const nextDay = day === 5 ? t('周一') : t('明天')
    nextShort = w ? pad(w[0]) : `${nextDay} 09:00`
    next = t('{0} 转高峰', nextShort)
  } else {
    nextShort = t('周一 09:00')
    next = t('{0} 转高峰', nextShort)
  }
  return { inPeak, weekday, next, nextShort }
}
