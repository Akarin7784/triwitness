import { Check, Coins, Hourglass, X } from 'lucide-react'
import clsx from 'clsx'
import type { Phase } from '../data/mapEvent'

/** 会话终态的小图形：完成 ✓ / 失败 ✕ / 触及安全上限 ¥ / 等待 ⧗ / 进行中呼吸点 */
export function StatusGlyph({ phase, className }: { phase: Phase; className?: string }) {
  const cls = clsx('shrink-0', className)
  switch (phase) {
    case 'done':
      return <Check size={12} strokeWidth={2} className={clsx(cls, 'text-sage')} />
    case 'failed':
      return <X size={12} strokeWidth={2} className={clsx(cls, 'text-rose-ink')} />
    case 'budget':
      return <Coins size={12} strokeWidth={1.8} className={clsx(cls, 'text-amber-ink')} />
    case 'waiting':
      return <Hourglass size={11} strokeWidth={1.8} className={clsx(cls, 'text-sepia')} />
    case 'cancelled':
      return <X size={12} strokeWidth={1.6} className={clsx(cls, 'text-sepia-muted')} />
    case 'active':
      return <span className={clsx(cls, 'pulse-dot h-1.5 w-1.5 rounded-full bg-amber')} />
    default:
      return <span className={clsx(cls, 'h-1.5 w-1.5 rounded-full bg-border')} />
  }
}
