import { useEffect, useRef, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { X } from 'lucide-react'
import clsx from 'clsx'
import { trackDialog } from '../lib/dialogState'
import { t as tr } from '../lib/i18n'


/**
 * 模态对话框：纸面卡片弹簧浮起 + 背景柔化；Esc / 点背景关闭；打开时把焦点放进去，关掉还给原处。
 */
export function Dialog({
  open,
  onClose,
  title,
  children,
  width = 440,
  testId,
  className,
  bare,
}: {
  open: boolean
  onClose: () => void
  title?: ReactNode
  children: ReactNode
  width?: number
  testId?: string
  className?: string
  /** 不要标题栏（搜索面板） */
  bare?: boolean
}) {
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const untrack = trackDialog()
    const prev = document.activeElement as HTMLElement | null
    const t = window.setTimeout(() => {
      const el = box.current?.querySelector<HTMLElement>('[autofocus],input,textarea,button[data-primary]')
      ;(el ?? box.current)?.focus()
    }, 30)
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        e.stopPropagation()
        onClose()
      }
    }
    window.addEventListener('keydown', key, true)
    return () => {
      untrack()
      window.clearTimeout(t)
      window.removeEventListener('keydown', key, true)
      prev?.focus?.()
    }
  }, [open, onClose])

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="dlg"
          className="fixed inset-0 z-[60] flex items-start justify-center px-4 pt-[14vh]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, transition: { duration: 0.16 } }}
        >
          <div className="absolute inset-0 bg-ink/20 backdrop-blur-[2px]" onPointerDown={onClose} aria-hidden />
          <motion.div
            ref={box}
            role="dialog"
            aria-modal="true"
            tabIndex={-1}
            data-testid={testId}
            initial={{ opacity: 0, y: 14, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98, transition: { duration: 0.14 } }}
            transition={{ type: 'spring', stiffness: 420, damping: 34, mass: 0.8 }}
            style={{ width }}
            className={clsx('menu-card relative max-w-full outline-none', !bare && 'p-5', className)}
          >
            {!bare && title && (
              <div className="mb-3 flex items-center justify-between gap-3">
                <h3 className="font-serif text-[16px] font-medium text-ink">{title}</h3>
                <button type="button" aria-label={tr('关闭')} onClick={onClose} className="tb-icon">
                  <X size={14} strokeWidth={1.6} />
                </button>
              </div>
            )}
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export function DialogActions({ children }: { children: ReactNode }) {
  return <div className="mt-5 flex items-center justify-end gap-2">{children}</div>
}

export function Btn({
  children,
  onClick,
  kind = 'ghost',
  disabled,
  testId,
  primary,
}: {
  children: ReactNode
  onClick?: () => void
  kind?: 'ghost' | 'solid' | 'danger'
  disabled?: boolean
  testId?: string
  primary?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      data-testid={testId}
      data-primary={primary || undefined}
      className={clsx(
        'rounded-lg px-3.5 py-1.5 text-[13px] transition-colors duration-300 disabled:cursor-not-allowed disabled:opacity-45',
        kind === 'solid' && 'bg-ink text-parchment hover:bg-espresso',
        kind === 'danger' && 'bg-rose-ink text-cream hover:bg-[#8f6658]',
        kind === 'ghost' && 'text-ink-soft hover:bg-panel-raised',
      )}
    >
      {children}
    </button>
  )
}
