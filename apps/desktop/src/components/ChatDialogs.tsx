import { useMemo, useState } from 'react'
import { MessageSquarePlus, Search, ShieldAlert, Star } from 'lucide-react'
import clsx from 'clsx'
import { Btn, Dialog, DialogActions } from './Dialog'
import { SHORTCUTS, keyLabel } from '../lib/shortcuts'
import { UNRESTRICTED_PHRASE } from '../bridge/choices'
import type { Rating } from '../lib/chats'

const FIELD =
  'w-full rounded-xl border border-border-soft bg-cream/70 px-3 py-2 text-[13.5px] text-ink outline-none transition-colors duration-300 placeholder:text-sepia-muted/70 focus:border-amber/60'

export function RenameDialog({
  open,
  initial,
  onClose,
  onSave,
}: {
  open: boolean
  initial: string
  onClose: () => void
  onSave: (title: string) => void
}) {
  return (
    <Dialog open={open} onClose={onClose} title="重命名" testId="rename-dialog">
      {open && <RenameBody initial={initial} onClose={onClose} onSave={onSave} />}
    </Dialog>
  )
}

function RenameBody({ initial, onClose, onSave }: { initial: string; onClose: () => void; onSave: (t: string) => void }) {
  const [v, setV] = useState(initial)
  const save = () => {
    onSave(v)
    onClose()
  }
  return (
    <>
      <input
        autoFocus
        value={v}
        onChange={(e) => setV(e.target.value)}
        onFocus={(e) => e.currentTarget.select()}
        onKeyDown={(e) => e.key === 'Enter' && !e.nativeEvent.isComposing && save()}
        maxLength={80}
        className={FIELD}
        aria-label="会话名"
      />
      <DialogActions>
        <Btn onClick={onClose}>取消</Btn>
        <Btn kind="solid" onClick={save} disabled={!v.trim()} testId="rename-save">
          保存
        </Btn>
      </DialogActions>
    </>
  )
}

export function ConfirmDeleteDialog({
  open,
  title,
  onClose,
  onConfirm,
}: {
  open: boolean
  title: string
  onClose: () => void
  onConfirm: () => void
}) {
  return (
    <Dialog open={open} onClose={onClose} title="删除会话" testId="delete-dialog">
      <p className="text-[13.5px] leading-relaxed text-ink-soft">
        确定删除<span className="font-serif text-ink">「{title}」</span>？
      </p>
      <DialogActions>
        <Btn onClick={onClose}>取消</Btn>
        <Btn
          kind="danger"
          primary
          testId="delete-confirm"
          onClick={() => {
            onConfirm()
            onClose()
          }}
        >
          删除
        </Btn>
      </DialogActions>
    </Dialog>
  )
}

export function FeedbackDialog({
  rating,
  onClose,
  onSubmit,
}: {
  rating: Rating | null
  onClose: () => void
  onSubmit: (note: string) => void
}) {
  return (
    <Dialog open={!!rating} onClose={onClose} title={rating === 'up' ? '有帮助' : '没帮助'} testId="feedback-dialog">
      {rating && <FeedbackBody rating={rating} onClose={onClose} onSubmit={onSubmit} />}
    </Dialog>
  )
}

function FeedbackBody({ rating, onClose, onSubmit }: { rating: Rating; onClose: () => void; onSubmit: (n: string) => void }) {
  const [v, setV] = useState('')
  return (
    <>
      <textarea
        autoFocus
        value={v}
        onChange={(e) => setV(e.target.value)}
        rows={4}
        placeholder={rating === 'up' ? '哪里好？' : '哪里不好？'}
        className={clsx(FIELD, 'resize-none leading-relaxed')}
        aria-label="反馈"
      />
      <DialogActions>
        <Btn onClick={onClose}>取消</Btn>
        <Btn
          kind="solid"
          testId="feedback-submit"
          onClick={() => {
            onSubmit(v)
            onClose()
          }}
        >
          提交
        </Btn>
      </DialogActions>
    </>
  )
}

export function ShortcutsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const groups = ['常用', '对话', '导航'] as const
  return (
    <Dialog open={open} onClose={onClose} title="快捷键" width={620} testId="shortcuts-dialog">
      <div className="grid gap-5 sm:grid-cols-2">
        {groups.map((g) => (
          <div key={g} className={clsx(g === '对话' && 'sm:row-span-2')}>
            <p className="mb-1.5 text-[10.5px] tracking-[0.14em] text-sepia-muted">{g}</p>
            {SHORTCUTS.filter((s) => s.group === g).map((s) => (
              <div key={s.action} className="flex items-center justify-between gap-3 py-1 text-[13px] text-ink-soft">
                <span>{s.label}</span>
                <span className="flex gap-1">
                  {s.keys.map((k) => (
                    <kbd key={k} className="kbd">
                      {keyLabel(k)}
                    </kbd>
                  ))}
                </span>
              </div>
            ))}
          </div>
        ))}
      </div>
    </Dialog>
  )
}

export interface PaletteItem {
  id: string
  title: string
  time?: string
  starred?: boolean
}

export function SearchPalette({
  open,
  items,
  onClose,
  onSelect,
  onNew,
}: {
  open: boolean
  items: PaletteItem[]
  onClose: () => void
  onSelect: (id: string) => void
  onNew: () => void
}) {
  return (
    <Dialog open={open} onClose={onClose} width={560} bare testId="search-palette">
      {open && <PaletteBody items={items} onClose={onClose} onSelect={onSelect} onNew={onNew} />}
    </Dialog>
  )
}

function PaletteBody({
  items,
  onClose,
  onSelect,
  onNew,
}: {
  items: PaletteItem[]
  onClose: () => void
  onSelect: (id: string) => void
  onNew: () => void
}) {
  const [q, setQ] = useState('')
  const [i, setI] = useState(0)
  const hits = useMemo(() => {
    const s = q.trim().toLowerCase()
    return s ? items.filter((x) => x.title.toLowerCase().includes(s)) : items
  }, [q, items])
  const rows = [{ id: '#new', title: '新会话' } as PaletteItem, ...hits]
  const pick = (r: PaletteItem) => {
    onClose()
    if (r.id === '#new') onNew()
    else onSelect(r.id)
  }
  return (
    <div>
      <div className="flex items-center gap-2.5 border-b border-border-soft px-4 py-3">
        <Search size={15} strokeWidth={1.6} className="text-sepia" />
        <input
          autoFocus
          value={q}
          onChange={(e) => {
            setQ(e.target.value)
            setI(e.target.value.trim() ? 1 : 0)
          }}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') {
              e.preventDefault()
              setI((n) => Math.min(rows.length - 1, n + 1))
            } else if (e.key === 'ArrowUp') {
              e.preventDefault()
              setI((n) => Math.max(0, n - 1))
            } else if (e.key === 'Enter' && !e.nativeEvent.isComposing && rows[i]) {
              e.preventDefault()
              pick(rows[i])
            }
          }}
          placeholder="搜索会话…"
          aria-label="搜索会话"
          className="flex-1 bg-transparent text-[14.5px] text-ink outline-none placeholder:text-sepia-muted/80"
        />
        <kbd className="kbd">Esc</kbd>
      </div>
      <div className="max-h-[50vh] overflow-y-auto scroll-soft p-1.5">
        {rows.map((r, n) => (
          <button
            key={r.id}
            type="button"
            data-active={n === i}
            onMouseMove={() => setI(n)}
            onClick={() => pick(r)}
            className="menu-item"
          >
            {r.id === '#new' ? (
              <MessageSquarePlus size={14} strokeWidth={1.6} className="text-amber" />
            ) : r.starred ? (
              <Star size={13} strokeWidth={1.6} className="fill-amber/70 text-amber" />
            ) : (
              <span className="w-[14px]" />
            )}
            <span className={clsx('min-w-0 flex-1 truncate', r.id !== '#new' && 'font-serif')}>{r.title}</span>
            {r.time && <span className="font-mono text-[10.5px] text-sepia-muted">{r.time}</span>}
          </button>
        ))}
        {hits.length === 0 && <p className="px-3 py-6 text-center text-[12.5px] text-sepia-muted">没有匹配的会话</p>}
      </div>
    </div>
  )
}

export function UnrestrictedDialog({
  open,
  onClose,
  onArm,
}: {
  open: boolean
  onClose: () => void
  onArm: () => void
}) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      width={460}
      testId="unrestricted-dialog"
      title={
        <span className="flex items-center gap-2 text-rose-ink">
          <ShieldAlert size={16} strokeWidth={1.7} />
          无限制（勇士模式）
        </span>
      }
    >
      {open && <UnrestrictedBody onClose={onClose} onArm={onArm} />}
    </Dialog>
  )
}

function UnrestrictedBody({ onClose, onArm }: { onClose: () => void; onArm: () => void }) {
  const [ack, setAck] = useState(false)
  const [typed, setTyped] = useState('')
  const ok = ack && typed.trim() === UNRESTRICTED_PHRASE
  return (
    <>
      <ul className="space-y-1.5 rounded-xl border border-rose-ink/30 bg-rose-ink/[0.06] px-4 py-3 text-[12.5px] leading-relaxed text-ink-soft">
        <li>不再询问任何操作，默认拒绝规则全部解除</li>
        <li>没有沙箱时，命令直接在你的电脑上运行</li>
        <li>只对下一个任务生效，结束自动恢复</li>
      </ul>
      <label className="mt-4 flex cursor-pointer items-center gap-2.5 text-[13px] text-ink-soft">
        <input
          type="checkbox"
          checked={ack}
          onChange={(e) => setAck(e.target.checked)}
          data-testid="unrestricted-ack"
          className="h-4 w-4 accent-[var(--color-rose-ink)]"
        />
        我知道没有任何确认和默认拒绝
      </label>
      <input
        value={typed}
        onChange={(e) => setTyped(e.target.value)}
        disabled={!ack}
        placeholder={`输入“${UNRESTRICTED_PHRASE}”`}
        aria-label="确认短语"
        data-testid="unrestricted-phrase"
        className={clsx(FIELD, 'mt-3 disabled:opacity-50')}
      />
      <DialogActions>
        <Btn onClick={onClose}>取消</Btn>
        <Btn
          kind="danger"
          disabled={!ok}
          testId="unrestricted-arm"
          onClick={() => {
            onArm()
            onClose()
          }}
        >
          开启
        </Btn>
      </DialogActions>
    </>
  )
}
