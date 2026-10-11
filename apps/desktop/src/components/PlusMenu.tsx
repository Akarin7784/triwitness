import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Camera, Check, ChevronLeft, ChevronRight, Globe, Palette, Paperclip, Pencil, Plug, Puzzle, Sparkles, Telescope, Plus } from 'lucide-react'
import clsx from 'clsx'
import { notYet } from '../lib/toast'
import { PRESET_STYLES, setPrefs, usePrefs } from '../lib/prefs'
import { Kbd, MenuDivider, Popover } from './Popover'
import { Tip } from './Tip'
import { t } from '../lib/i18n'

const STUBS = [
  { icon: Camera, label: t('截图') },
  null,
  { icon: Globe, label: t('网页搜索') },
  { icon: Telescope, label: t('深度研究') },
  null,
  { icon: Sparkles, label: t('技能') },
  { icon: Plug, label: t('连接器') },
  { icon: Puzzle, label: t('插件') },
] as const

/** 输入框左下角的 +：与 Claude 同一组入口。附件、风格已实现；其余点了给一句“即将推出” */
export function PlusMenu({
  open,
  onOpenChange,
  onAttach,
  onEditStyles,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  onAttach: () => void
  onEditStyles: () => void
}) {
  const [page, setPage] = useState<'main' | 'style'>('main')
  const prefs = usePrefs()
  const close = () => {
    onOpenChange(false)
    window.setTimeout(() => setPage('main'), 200)
  }
  const styles = [...PRESET_STYLES.map((s) => ({ id: s.id, name: s.name })), ...prefs.customStyles.map((c) => ({ id: c.id, name: c.name }))]
  return (
    <div className="relative">
      <Tip label={t('添加')} side="top-start">
        <button
          type="button"
          aria-label={t('添加')}
          data-testid="plus-button"
          aria-haspopup="menu"
          aria-expanded={open}
          onClick={() => (open ? close() : onOpenChange(true))}
          className={clsx(
            'inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border-soft text-sepia transition-all duration-300 hover:border-border hover:text-amber-ink',
            open && 'border-border bg-panel-raised text-amber-ink',
          )}
        >
          <Plus size={15} strokeWidth={1.7} className={clsx('transition-transform duration-300', open && 'rotate-45')} />
        </button>
      </Tip>
      <Popover open={open} onClose={close} className="w-[236px] overflow-hidden" testId="plus-menu">
        <AnimatePresence mode="popLayout" initial={false}>
          {page === 'main' ? (
            <motion.div
              key="main"
              initial={{ opacity: 0, x: -16 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ pointerEvents: 'none', opacity: 0, x: -16 }}
              transition={{ type: 'spring', stiffness: 520, damping: 38 }}
            >
              <button
                type="button"
                role="menuitem"
                data-testid="plus-attach"
                className="menu-item"
                onClick={() => {
                  close()
                  onAttach()
                }}
              >
                <Paperclip size={14} strokeWidth={1.6} className="text-sepia" />
                <span>{t('添加文件或图片')}</span>
                <Kbd>Ctrl U</Kbd>
              </button>
              {STUBS.map((it, i) =>
                it === null ? (
                  <MenuDivider key={i} />
                ) : (
                  <button
                    key={it.label}
                    type="button"
                    role="menuitem"
                    className="menu-item"
                    onClick={() => {
                      close()
                      notYet(it.label)
                    }}
                  >
                    <it.icon size={14} strokeWidth={1.6} className="text-sepia" />
                    <span>{it.label}</span>
                  </button>
                ),
              )}
              <MenuDivider />
              <button type="button" role="menuitem" data-testid="plus-style" className="menu-item" onClick={() => setPage('style')}>
                <Palette size={14} strokeWidth={1.6} className="text-sepia" />
                <span>{t('风格')}</span>
                <span className="ml-auto flex items-center gap-1 pl-3 text-[11.5px] text-sepia-muted">
                  {styles.find((s) => s.id === prefs.style)?.name}
                  <ChevronRight size={12} />
                </span>
              </button>
            </motion.div>
          ) : (
            <motion.div
              key="style"
              data-testid="style-menu"
              initial={{ opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ pointerEvents: 'none', opacity: 0, x: 16 }}
              transition={{ type: 'spring', stiffness: 520, damping: 38 }}
            >
              <button type="button" className="menu-item text-sepia" onClick={() => setPage('main')}>
                <ChevronLeft size={14} strokeWidth={1.6} />
                <span>{t('风格')}</span>
              </button>
              <MenuDivider />
              {styles.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  role="menuitemradio"
                  aria-checked={prefs.style === s.id}
                  data-testid={`style-${s.id}`}
                  className="menu-item"
                  onClick={() => {
                    setPrefs({ style: s.id })
                    close()
                  }}
                >
                  <span className="w-[14px]">{prefs.style === s.id && <Check size={13} strokeWidth={2} className="text-amber-ink" />}</span>
                  <span className="truncate">{s.name}</span>
                </button>
              ))}
              <MenuDivider />
              <button
                type="button"
                className="menu-item"
                data-testid="style-edit"
                onClick={() => {
                  close()
                  onEditStyles()
                }}
              >
                <Pencil size={13} strokeWidth={1.6} className="text-sepia" />
                <span>{t('创建并编辑风格')}</span>
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </Popover>
    </div>
  )
}
