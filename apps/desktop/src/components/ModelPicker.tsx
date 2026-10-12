import { useState } from 'react'
import { Check, ChevronDown, ChevronRight } from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'
import clsx from 'clsx'
import { MODELS, THINKING_LEVELS, setPrefs, usePrefs } from '../lib/prefs'
import { notYet } from '../lib/toast'
import { Popover, MenuDivider } from './Popover'
import { t as tr } from '../lib/i18n'

const DEFAULT_THINKING = 'medium'

/** Claude 式模型选择：输入框右下角；模型列表（一行说明）· 思考强度子菜单 · 更多模型 */
export function ModelPicker({
  open,
  onOpenChange,
  effort,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  /** Ctrl+Shift+E：打开时直接展开思考强度 */
  effort?: boolean
}) {
  const prefs = usePrefs()
  const [subState, setSub] = useState(false)
  const sub = subState || !!effort
  const model = MODELS.find((m) => m.id === prefs.model) ?? MODELS[0]
  const level = THINKING_LEVELS.find((t) => t.id === prefs.thinking)!
  const close = () => {
    setSub(false)
    onOpenChange(false)
  }
  return (
    <div className="relative min-w-0">
      <button
        type="button"
        data-testid="model-picker"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => onOpenChange(!open)}
        className={clsx(
          'inline-flex h-8 min-w-0 max-w-full items-center gap-1 whitespace-nowrap rounded-lg px-2 text-[13px] text-ink-soft transition-colors duration-300 hover:bg-panel-raised',
          open && 'bg-panel-raised',
        )}
      >
        <span className="min-w-[4.5em] truncate">{model.name}</span>
        {/* 输入框太窄时先藏“思考 中”，保证模型名和仓库签都看得见（不换行） */}
        {prefs.thinking !== 'off' && <span className="hidden shrink-0 text-sepia-muted @[400px]:inline">{tr('· 思考 {0}', level.label)}</span>}
        <ChevronDown size={13} strokeWidth={1.7} className={clsx('shrink-0 text-sepia-muted transition-transform duration-300', open && 'rotate-180')} />
      </button>
      <Popover open={open} onClose={close} align="right" className="w-[264px]" testId="model-menu">
        {MODELS.map((m) => (
          <button
            key={m.id}
            type="button"
            role="menuitemradio"
            aria-checked={m.id === prefs.model}
            disabled={!m.available}
            onClick={() => {
              setPrefs({ model: m.id })
              close()
            }}
            className="menu-item items-start"
          >
            <span className="flex min-w-0 flex-1 flex-col">
              <span className={clsx(m.available ? 'text-ink' : 'text-sepia-muted')}>{m.name}</span>
              <span className="text-[13px] text-sepia-muted">{m.note}</span>
            </span>
            {m.id === prefs.model && <Check size={14} strokeWidth={1.8} className="mt-0.5 text-amber-ink" />}
          </button>
        ))}
        <MenuDivider />
        <div className="relative" onMouseLeave={() => setSub(false)}>
          <button
            type="button"
            data-testid="effort-item"
            onMouseEnter={() => setSub(true)}
            onClick={() => setSub((s) => !s)}
            data-active={sub}
            className="menu-item"
          >
            <span className="flex-1">{tr('思考强度')}</span>
            <span className="text-[13px] text-sepia-muted">{level.label}</span>
            <ChevronRight size={13} strokeWidth={1.7} className="text-sepia-muted" />
          </button>
          <AnimatePresence>
            {sub && (
              <motion.div
                role="menu"
                data-testid="effort-menu"
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ pointerEvents: 'none', opacity: 0, x: -4, transition: { duration: 0.12 } }}
                transition={{ type: 'spring', stiffness: 520, damping: 36 }}
                className="menu-card absolute bottom-0 left-[calc(100%+6px)] w-[150px] p-1.5"
              >
                {[...THINKING_LEVELS].reverse().map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    role="menuitemradio"
                    aria-checked={t.id === prefs.thinking}
                    onClick={() => {
                      setPrefs({ thinking: t.id })
                      close()
                    }}
                    className="menu-item"
                  >
                    <span className="flex-1">{t.label}</span>
                    {t.id === DEFAULT_THINKING && <span className="text-[13px] text-sepia-muted">{tr('默认')}</span>}
                    {t.id === prefs.thinking && <Check size={13} strokeWidth={1.8} className="text-amber-ink" />}
                  </button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
        <button type="button" onClick={() => (close(), notYet(tr('更多模型')))} className="menu-item">
          <span className="flex-1">{tr('更多模型')}</span>
          <ChevronRight size={13} strokeWidth={1.7} className="text-sepia-muted" />
        </button>
      </Popover>
    </div>
  )
}
