import { useMemo, useState } from 'react'
import clsx from 'clsx'
import { Check, FolderClosed, MessageSquarePlus, MessagesSquare, Search, Star, Trash2, X } from 'lucide-react'
import type { SidebarItem } from './Sidebar'
import { StatusGlyph } from './StatusGlyph'
import { Btn, Dialog, DialogActions } from './Dialog'
import { FIELD } from '../lib/ui'
import { locale, t as tr } from '../lib/i18n'

/** 相对时间：今天显示时刻，今年显示月日，更早显示年月日 */
function when(at: number | undefined, time: string | undefined): string {
  if (!at) return time ?? ''
  const d = new Date(at)
  const now = new Date()
  if (d.toDateString() === now.toDateString()) return d.toTimeString().slice(0, 5)
  const opts: Intl.DateTimeFormatOptions = d.getFullYear() === now.getFullYear() ? { month: 'short', day: 'numeric' } : { year: 'numeric', month: 'short', day: 'numeric' }
  return d.toLocaleDateString(locale(), opts)
}

/**
 * 会话页（BUG4，照 Claude 的 “Chats”）：全部会话按最近排序 · 搜索 · 选择 / 批量删除。
 * 行高固定，悬停只改背景；选择模式下行首出现复选框。
 */
export function ChatsPage({
  items,
  projects,
  onOpen,
  onNew,
  onDelete,
}: {
  items: SidebarItem[]
  projects: { id: string; name: string }[]
  onOpen: (id: string) => void
  onNew: () => void
  onDelete: (ids: string[]) => void
}) {
  const [q, setQ] = useState('')
  const [selecting, setSelecting] = useState(false)
  const [picked, setPicked] = useState<Set<string>>(new Set())
  const [confirm, setConfirm] = useState(false)
  const sorted = useMemo(() => [...items].sort((a, b) => (b.at ?? 0) - (a.at ?? 0)), [items])
  const needle = q.trim().toLowerCase()
  const shown = needle ? sorted.filter((i) => i.title.toLowerCase().includes(needle)) : sorted
  const projectName = (pid?: string | null) => (pid ? projects.find((p) => p.id === pid)?.name : undefined)
  const toggle = (id: string) =>
    setPicked((s) => {
      const n = new Set(s)
      if (n.has(id)) n.delete(id)
      else n.add(id)
      return n
    })
  const allPicked = shown.length > 0 && shown.every((i) => picked.has(i.id))
  const exitSelect = () => (setSelecting(false), setPicked(new Set()))
  return (
    <main data-testid="chats-page" className="min-w-0 flex-1 overflow-y-auto scroll-soft">
      <div className="mx-auto max-w-[860px] px-12 py-10">
        <div className="flex items-center justify-between gap-4">
          <h1 className="chapter-title font-serif text-[26px] text-ink">{tr('会话')}</h1>
          <Btn kind="solid" onClick={onNew} testId="chats-new">
            <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
              <MessageSquarePlus size={14} /> {tr('新会话')}
            </span>
          </Btn>
        </div>
        <div className="relative mt-6">
          <Search size={14} strokeWidth={1.7} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sepia-muted" />
          <input
            data-testid="chats-search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={tr('搜索会话…')}
            aria-label={tr('搜索会话')}
            className={clsx(FIELD, 'pl-9')}
          />
        </div>
        <div className="mt-4 flex h-8 items-center gap-3 text-[12.5px] text-sepia">
          {selecting ? (
            <>
              <button type="button" data-testid="chats-select-all" onClick={() => setPicked(allPicked ? new Set() : new Set(shown.map((i) => i.id)))} className="whitespace-nowrap rounded-md px-1.5 py-1 hover:bg-panel-raised hover:text-ink">
                {allPicked ? tr('取消全选') : tr('全选')}
              </button>
              <span className="whitespace-nowrap text-sepia-muted">{tr('已选 {0} 个', picked.size)}</span>
              <span className="ml-auto flex items-center gap-1">
                <button
                  type="button"
                  data-testid="chats-delete"
                  disabled={!picked.size}
                  onClick={() => setConfirm(true)}
                  className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-2 py-1 text-rose-ink hover:bg-rose-ink/10 disabled:opacity-40"
                >
                  <Trash2 size={13} strokeWidth={1.7} /> {tr('删除')}
                </button>
                <button type="button" aria-label={tr('退出选择')} onClick={exitSelect} className="inline-flex h-7 w-7 items-center justify-center rounded-md hover:bg-panel-raised hover:text-ink">
                  <X size={14} strokeWidth={1.7} />
                </button>
              </span>
            </>
          ) : (
            <>
              <span className="whitespace-nowrap text-sepia-muted">{tr('共 {0} 个会话', shown.length)}</span>
              {shown.length > 0 && (
                <button type="button" data-testid="chats-select" onClick={() => setSelecting(true)} className="ml-auto whitespace-nowrap rounded-md px-1.5 py-1 hover:bg-panel-raised hover:text-ink">
                  {tr('选择')}
                </button>
              )}
            </>
          )}
        </div>
        {shown.length === 0 ? (
          <div className="mt-16 flex flex-col items-center text-center">
            <MessagesSquare size={28} strokeWidth={1.3} className="text-sepia-muted" />
            <p className="mt-3 font-serif text-[16px] text-ink">{needle ? tr('没有匹配的会话') : tr('还没有会话')}</p>
          </div>
        ) : (
          <ul data-testid="chats-list" className="mt-2 divide-y divide-border-soft/70 border-y border-border-soft/70">
            {shown.map((i) => {
              const on = picked.has(i.id)
              const pname = projectName(i.projectId)
              return (
                <li key={i.id}>
                  <button
                    type="button"
                    data-testid="chats-row"
                    aria-pressed={selecting ? on : undefined}
                    onClick={() => (selecting ? toggle(i.id) : onOpen(i.id))}
                    className={clsx('flex h-[58px] w-full items-center gap-3 px-3 text-left transition-colors duration-200 hover:bg-panel-raised/70', on && 'bg-amber/[0.08]')}
                  >
                    {selecting && (
                      <span className={clsx('flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors duration-200', on ? 'border-amber-ink bg-amber-ink text-parchment' : 'border-border')}>
                        {on && <Check size={11} strokeWidth={2.4} />}
                      </span>
                    )}
                    <span className="flex w-4 shrink-0 justify-center">{i.phase ? <StatusGlyph phase={i.phase} /> : null}</span>
                    <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                      <span className="flex min-w-0 items-center gap-1.5">
                        {i.starred && <Star size={12} strokeWidth={1.6} className="shrink-0 fill-amber/70 text-amber-ink" />}
                        <span className="truncate font-serif text-[14.5px] text-ink">{i.title}</span>
                      </span>
                      <span className="flex min-w-0 items-center gap-2 text-[11.5px] text-sepia-muted">
                        {i.label && <span className="shrink-0 whitespace-nowrap">{i.label}</span>}
                        {pname && (
                          <span className="inline-flex min-w-0 items-center gap-1">
                            <FolderClosed size={11} strokeWidth={1.6} className="shrink-0" />
                            <span className="truncate">{pname}</span>
                          </span>
                        )}
                      </span>
                    </span>
                    <span className="w-[72px] shrink-0 text-right font-mono text-[11px] tabular-nums text-sepia-muted">{when(i.at, i.time)}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>
      <Dialog open={confirm} onClose={() => setConfirm(false)} title={tr('删除会话')} testId="chats-delete-dialog">
        <p className="text-[13.5px] leading-relaxed text-ink-soft">{tr('确定删除选中的 {0} 个会话？删除后不能恢复。', picked.size)}</p>
        <DialogActions>
          <Btn onClick={() => setConfirm(false)}>{tr('取消')}</Btn>
          <Btn
            kind="danger"
            primary
            testId="chats-delete-confirm"
            onClick={() => {
              onDelete([...picked])
              setConfirm(false)
              exitSelect()
            }}
          >
            {tr('删除')}
          </Btn>
        </DialogActions>
      </Dialog>
    </main>
  )
}
