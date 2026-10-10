/** 轻提示（UI-20）：未做的功能入口点一下，底部浮出一句，2 秒后淡出 */
import { useSyncExternalStore } from 'react'
import { t as tr } from './i18n'

export interface Toast {
  id: number
  text: string
}

let toasts: Toast[] = []
let n = 0
const subs = new Set<() => void>()
const emit = () => subs.forEach((s) => s())

export function toast(text: string, ms = 2200) {
  const t = { id: ++n, text }
  toasts = [...toasts.filter((x) => x.text !== text), t].slice(-3)
  emit()
  setTimeout(() => {
    toasts = toasts.filter((x) => x.id !== t.id)
    emit()
  }, ms)
}

/** 功能入口已就位、实现还没到：统一口径 */
export function notYet(feature: string) {
  toast(tr('{0} · 即将推出', feature))
}

export function useToasts(): Toast[] {
  return useSyncExternalStore(
    (fn) => {
      subs.add(fn)
      return () => subs.delete(fn)
    },
    () => toasts,
  )
}
