import { useCallback, useState } from 'react'
import clsx from 'clsx'
import { BookMarked, ChevronDown } from 'lucide-react'
import type { MemoryUsed } from '../data/memory'
import { shortSource } from '../data/memory'
import { Popover } from './Popover'
import { t } from '../lib/i18n'

/** 标题栏小芯片「记忆 N」：点开列出本次注入的仓库事实与技能（带来源）。没有记忆时不渲染。 */
export function MemoryChip({ memory }: { memory: MemoryUsed | null }) {
  const [open, setOpen] = useState(false)
  const close = useCallback(() => setOpen(false), [])
  if (!memory) return null
  const n = memory.factsTotal + memory.skillsTotal
  return (
    <span className="relative inline-flex">
      <button
        type="button"
        data-testid="memory-chip"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t('本次用了 {0} 条记忆', n)}
        onClick={() => setOpen((o) => !o)}
        className={clsx('chip cursor-pointer transition-colors duration-300 hover:text-amber-ink', open && 'text-amber-ink')}
      >
        <BookMarked size={11} strokeWidth={1.7} className="shrink-0" />
        <span className="tabular-nums">{t('记忆 {0}', n)}</span>
        <ChevronDown size={10} strokeWidth={1.8} className={clsx('shrink-0 transition-transform duration-300', open && 'rotate-180')} />
      </button>
      <Popover open={open} onClose={close} side="down" align="right" testId="memory-panel" className="w-[340px] max-w-[80vw]">
        <div className="max-h-[360px] overflow-y-auto scroll-soft px-2 py-1.5 text-[12px]">
          <p className="pb-1.5 font-serif text-[13px] text-ink">{t('本次用了这些记忆')}</p>
          {memory.factsTotal > 0 && (
            <Section title={t('仓库事实')} total={memory.factsTotal} shown={memory.facts.length}>
              {memory.facts.map((f) => (
                <Item key={f.id} text={f.text} tag={f.kind} source={f.source} />
              ))}
            </Section>
          )}
          {memory.skillsTotal > 0 && (
            <Section title={t('技能')} total={memory.skillsTotal} shown={memory.skills.length}>
              {memory.skills.map((s) => (
                <Item
                  key={s.name}
                  text={s.description ? `${s.name} — ${s.description}` : s.name}
                  tag={s.version !== null ? `v${s.version}` : null}
                  source={s.source}
                />
              ))}
            </Section>
          )}
          <p className="border-t border-border-soft pt-1.5 text-[10.5px] leading-relaxed text-sepia-muted">
            {memory.episodes ? t('另会按问题检索相似经验；') : ''}
            {t('记忆是参考数据，与仓库现状冲突时以仓库为准。不想用：tw run --no-memory')}
          </p>
        </div>
      </Popover>
    </span>
  )
}

function Section({ title, total, shown, children }: { title: string; total: number; shown: number; children: React.ReactNode }) {
  return (
    <div className="pb-2">
      <p className="pb-1 text-[10.5px] uppercase tracking-wider text-sepia-muted">
        {title} · {total}
        {shown < total ? ` ${t('（显示前 {0} 条）', shown)}` : ''}
      </p>
      <ul className="space-y-1">{children}</ul>
    </div>
  )
}

function Item({ text, tag, source }: { text: string; tag: string | null; source: string | null }) {
  const src = shortSource(source)
  return (
    <li data-testid="memory-item" className="rounded-md px-1.5 py-1 hover:bg-panel-raised">
      <p className="leading-snug text-ink-soft">{text}</p>
      {(tag || src) && (
        <p className="mt-0.5 flex gap-2 font-mono text-[10px] text-sepia-muted">
          {tag && <span>{tag}</span>}
          {src && <span title={source ?? undefined}>{t('来源 {0}', src)}</span>}
        </p>
      )}
    </li>
  )
}
