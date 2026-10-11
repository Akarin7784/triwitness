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
