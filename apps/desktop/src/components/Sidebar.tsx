import { PenLine, Settings } from 'lucide-react'
import clsx from 'clsx'
import type { Conversation } from '../types'
import { Tip } from './Tip'

interface SidebarProps {
  items: Conversation[]
  activeId: string
  onSelect: (id: string) => void
  onNew: () => void
  onSettings: () => void
  settingsActive?: boolean
}

export function Sidebar({ items, activeId, onSelect, onNew, onSettings, settingsActive }: SidebarProps) {
  return (
    <aside className="flex h-full w-[248px] shrink-0 flex-col border-r border-border-soft bg-panel/70">
      <div className="px-3 pb-2 pt-3">
        <button
          type="button"
          onClick={onNew}
          className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-[13px] text-ink-soft transition-colors duration-300 hover:bg-panel-raised"
        >
          <PenLine size={15} strokeWidth={1.6} className="text-amber" />
          新会话
        </button>
      </div>

      <p className="px-6 pb-1.5 pt-3 text-[10.5px] tracking-[0.14em] text-sepia-muted">近期</p>

      <nav className="min-h-0 flex-1 space-y-px overflow-y-auto scroll-soft px-2 pb-4">
        {items.map((c) => {
          const active = !settingsActive && c.id === activeId
          return (
            <button
              key={c.id}
              type="button"
              onClick={() => onSelect(c.id)}
              className={clsx(
                'group flex w-full items-center gap-2 rounded-lg px-4 py-2 text-left transition-colors duration-300',
                active ? 'bg-panel-raised shadow-[0_1px_0_rgb(212_196_168/0.6)]' : 'hover:bg-panel-raised/60',
              )}
            >
              <span
                className={clsx(
                  'min-w-0 flex-1 truncate font-serif text-[13px]',
                  active ? 'text-ink' : 'text-ink-soft/90',
                )}
              >
                {c.title}
              </span>
              <span className="shrink-0 text-[10px] text-sepia-muted opacity-0 transition-opacity duration-300 group-hover:opacity-100">
                {c.updatedAt}
              </span>
            </button>
          )
        })}
      </nav>

      <div className="border-t border-border-soft/80 p-2">
        <Tip label="设置与预算" side="top-start" className="w-full">
          <button
            type="button"
            onClick={onSettings}
            aria-label="设置与预算"
            className={clsx(
              'flex w-full items-center gap-2.5 rounded-lg px-4 py-2 text-[12.5px] transition-colors duration-300 hover:bg-panel-raised',
              settingsActive ? 'bg-panel-raised text-ink' : 'text-sepia',
            )}
          >
            <Settings size={14} strokeWidth={1.6} />
            设置
          </button>
        </Tip>
      </div>
    </aside>
  )
}
