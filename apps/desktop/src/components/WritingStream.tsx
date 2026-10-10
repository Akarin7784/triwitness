import { useEffect, useMemo, useRef } from 'react'
import { Pause, Play, RotateCcw } from 'lucide-react'
import clsx from 'clsx'
import type { StreamLine } from '../types'
import { roleColor, roleLabel } from '../data/mock'
import { useWritingStream, type WrittenChar } from '../hooks/useWritingStream'
import { useReducedMotion } from '../hooks/useReducedMotion'
import { Tip } from './Tip'

interface WritingStreamProps {
  lines: StreamLine[]
  className?: string
  autoStart?: boolean
  title?: string
  /** 重播时通知数据源从头推送（流式 mock 用） */
  onRestart?: () => void
}

export function WritingStream({
  lines,
  className,
  autoStart = true,
  title = 'SSH',
  onRestart,
}: WritingStreamProps) {
  const reduced = useReducedMotion()
  const { chars, visibleCount, playing, done, toggle, restart, progress } = useWritingStream({
    lines,
    autoStart,
    reducedMotion: reduced,
  })

  const scrollRef = useRef<HTMLDivElement>(null)
  const pinnedRef = useRef(true)

  // 只有用户停在底部时才跟随，往上翻看历史时不打扰
  useEffect(() => {
    const el = scrollRef.current
    if (!el || !pinnedRef.current) return
    el.scrollTo({ top: el.scrollHeight, behavior: reduced ? 'auto' : 'smooth' })
  }, [visibleCount, reduced])

  const grouped = useMemo(() => {
    const out: { lineId: string; role: StreamLine['role']; items: WrittenChar[] }[] = []
    for (let i = 0; i < visibleCount; i++) {
      const c = chars[i]
      const cur = out[out.length - 1]
      if (!cur || cur.lineId !== c.lineId) out.push({ lineId: c.lineId, role: c.role, items: [c] })
      else cur.items.push(c)
    }
    return out
  }, [chars, visibleCount])

  const activeRole = grouped[grouped.length - 1]?.role
  const state: 'writing' | 'paused' | 'idle' | 'done' = done
    ? 'done'
    : !playing
      ? 'paused'
      : visibleCount < chars.length
        ? 'writing'
        : 'idle'
  const stateTip = {
    writing: `落笔 · ${activeRole ? roleLabel[activeRole] : ''}`,
    paused: '已暂停',
    idle: '等待下一行',
    done: '写毕',
  }[state]
  const stateColor = {
    writing: activeRole ? roleColor[activeRole] : 'var(--color-amber)',
    paused: 'var(--color-sepia-muted)',
    idle: 'var(--color-amber-soft)',
    done: 'var(--color-sage)',
  }[state]

  const handleRestart = () => {
    onRestart?.()
    restart()
  }

  return (
    <div className={clsx('flex h-full min-h-0 flex-col', className)}>
      <div className="flex items-center justify-between gap-3 px-5 pb-3.5 pt-5">
        <div className="flex min-w-0 items-center gap-3">
          <h2 className="truncate font-serif text-[16px] font-medium tracking-wide text-ink">{title}</h2>
          <div className="flex items-center gap-1.5">
            {(['planner', 'executor', 'verifier', 'reviewer'] as const).map((r) => (
              <Tip key={r} label={roleLabel[r]} side="bottom">
                <span
                  className={clsx('role-dot transition-opacity duration-500', activeRole && activeRole !== r && 'opacity-35')}
                  style={{ background: roleColor[r] }}
                />
              </Tip>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Tip label={stateTip} side="bottom">
            <span className="flex h-7 w-5 items-center justify-center">
              <span
                className={clsx('h-1.5 w-1.5 rounded-full transition-colors duration-700', state === 'writing' && 'pulse-dot')}
                style={{ background: stateColor }}
              />
            </span>
          </Tip>
          <IconButton
            onClick={done ? handleRestart : toggle}
            label={done ? '重播' : playing ? '暂停' : '继续'}
          >
            {done ? <RotateCcw size={13} strokeWidth={1.6} /> : playing ? <Pause size={13} strokeWidth={1.6} /> : <Play size={13} strokeWidth={1.6} />}
          </IconButton>
          {!done && (
            <IconButton onClick={handleRestart} label="从头">
              <RotateCcw size={13} strokeWidth={1.6} />
            </IconButton>
          )}
        </div>
      </div>

      <div className="mx-5 h-px bg-border-soft">
        <div
          className="h-px origin-left bg-amber/60 transition-transform duration-700 ease-[var(--ease-tender)]"
          style={{ transform: `scaleX(${progress})` }}
        />
      </div>

      <div
        ref={scrollRef}
        onScroll={(e) => {
          const el = e.currentTarget
          pinnedRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48
        }}
        className="stream-paper relative min-h-0 flex-1 overflow-y-auto scroll-soft px-5 py-5"
      >
        <div className="selectable font-mono text-[12.5px] leading-[1.85] text-ink-soft">
          {grouped.map((line, li) => {
            const isLast = li === grouped.length - 1
            return (
              <div key={line.lineId} className="stream-line relative mb-3 flex gap-3">
                <span className="relative mt-[0.62em] flex h-[7px] w-[7px] shrink-0">
                  <span className="ink-bloom" style={{ background: `radial-gradient(circle, ${roleColor[line.role]}55, transparent 70%)` }} />
                  <span className="role-dot" style={{ background: roleColor[line.role] }} />
                </span>
                <p className="min-w-0 flex-1 whitespace-pre-wrap break-words">
                  <span
                    className="mr-2 inline-block select-none font-sans text-[10.5px] font-medium tracking-[0.12em]"
                    style={{ color: roleColor[line.role] }}
                  >
                    {roleLabel[line.role]}
                  </span>
                  {line.items.map((c) => (
                    <span key={c.key} className="ink-char">
                      {c.ch}
                    </span>
                  ))}
                  {isLast && !done && <span className={clsx('caret-ink', !playing && 'caret-rest')} aria-hidden />}
                </p>
              </div>
            )
          })}

          {visibleCount === 0 && <span className="caret-ink" aria-hidden />}
        </div>
      </div>
    </div>
  )
}

function IconButton({ onClick, label, children }: { onClick: () => void; label: string; children: React.ReactNode }) {
  return (
    <Tip label={label} side="bottom">
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-border-soft bg-panel-raised/80 text-sepia transition-colors duration-500 hover:border-amber-soft hover:text-amber"
    >
      {children}
    </button>
    </Tip>
  )
}
