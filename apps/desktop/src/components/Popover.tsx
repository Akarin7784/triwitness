import { useEffect, useRef, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import clsx from 'clsx'
import type { LucideIcon } from 'lucide-react'

/** 向上弹出的菜单（弹簧缩放 + 淡入，原点在锚点一侧）；点外面 / Esc 关闭 */
export function Popover({
  open,
  onClose,
  align = 'left',
  side = 'up',
  className,
  children,
  testId,
}: {
  open: boolean
  onClose: () => void
  align?: 'left' | 'right'
  /** 向上（输入框里）或向下（侧栏 / 标题栏）弹出 */
  side?: 'up' | 'down'
  className?: string
  children: ReactNode
  testId?: string
}) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const down = (e: PointerEvent) => {
      const host = ref.current?.parentElement
      if (host && !host.contains(e.target as Node)) onClose()
    }
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        onClose()
      }
    }
    window.addEventListener('pointerdown', down)
    window.addEventListener('keydown', key, true)
    return () => {
      window.removeEventListener('pointerdown', down)
      window.removeEventListener('keydown', key, true)
    }
  }, [open, onClose])
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          ref={ref}
          role="menu"
          data-testid={testId}
          initial={{ opacity: 0, y: side === 'up' ? 6 : -6, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: side === 'up' ? 4 : -4, scale: 0.98, transition: { duration: 0.14 } }}
          transition={{ type: 'spring', stiffness: 520, damping: 34, mass: 0.7 }}
          style={{ transformOrigin: `${side === 'up' ? 'bottom' : 'top'} ${align}` }}
          className={clsx(
            'menu-card absolute z-40 p-1.5',
            side === 'up' ? 'bottom-[calc(100%+8px)]' : 'top-[calc(100%+6px)]',
            align === 'left' ? 'left-0' : 'right-0',
            className,
          )}
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export function MenuDivider() {
  return <div className="mx-2 my-1 h-px bg-border-soft" />
}

export function Kbd({ children }: { children: ReactNode }) {
  return <span className="ml-auto pl-3 font-mono text-[10.5px] tracking-wide text-sepia-muted">{children}</span>
}

export function MenuItem({
  icon: Icon,
  label,
  onClick,
  danger,
  kbd,
  testId,
}: {
  icon: LucideIcon
  label: string
  onClick: () => void
  danger?: boolean
  kbd?: string
  testId?: string
}) {
  return (
    <button type="button" role="menuitem" onClick={onClick} data-testid={testId} className={clsx('menu-item', danger && 'text-rose-ink')}>
      <Icon size={14} strokeWidth={1.6} className={danger ? 'text-rose-ink' : 'text-sepia'} />
      <span>{label}</span>
      {kbd && <Kbd>{kbd}</Kbd>}
    </button>
  )
}

