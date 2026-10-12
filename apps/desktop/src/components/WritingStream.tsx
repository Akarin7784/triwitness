import { memo, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Pause, Play, RotateCcw } from 'lucide-react'
import clsx from 'clsx'
import type { StreamLine } from '../types'
import { roleColor, roleLabel } from '../data/mock'
import { useWritingStream } from '../hooks/useWritingStream'
import { useReducedMotion } from '../hooks/useReducedMotion'
import { Tip } from './Tip'
import { t } from '../lib/i18n'
import { middlePath } from '../lib/streamText'

interface WritingStreamProps {
  lines: StreamLine[]
  className?: string
  autoStart?: boolean
  title?: string
  /** 重播时通知数据源从头推送 */
  onRestart?: () => void
  /** 笔尖开始写某一行时回调该行（用于让状态 / 对话 / 费用与书写同步）；清空时传 null */
  onReveal?: (line: StreamLine | null) => void
  /** 外部给定的当前角色（事件驱动时由 RunView 提供） */
  activeRole?: StreamLine['role'] | null
  /** 会话标识：切走再切回时恢复已显示行数与滚动位置，不从头重播（走查 r2-5） */
  sessionKey?: string
  /** 全部行写完 / 有新行开始写时回调（状态签终态等它） */
  onDone?: (done: boolean) => void
}

/** 每个会话看到哪一行、滚到哪里（进程内记忆，切会话不丢） */
const sessionMemo = new Map<string, { lines: number; scrollTop: number; pinned: boolean }>()

export function WritingStream({
  lines,
  className,
  autoStart = true,
  title = 'SSH',
  onRestart,
  onReveal,
  activeRole: roleOverride,
  sessionKey,
  onDone,
}: WritingStreamProps) {
  const reduced = useReducedMotion()
  const [memo0] = useState(() => (sessionKey ? sessionMemo.get(sessionKey) : undefined))
  const { chars, visibleCount, playing, done, toggle, restart, progress } = useWritingStream({
    lines,
    autoStart,
    reducedMotion: reduced,
    skipLines: memo0?.lines ?? 0,
  })

  const scrollRef = useRef<HTMLDivElement>(null)
  const pinnedRef = useRef(memo0?.pinned ?? true)
  const restoredRef = useRef(!memo0)

  // 切回会话：首次把已看过的行铺出来后，恢复上次的滚动位置
  useLayoutEffect(() => {
    const el = scrollRef.current
    if (restoredRef.current || !el || !memo0 || visibleCount === 0) return
    restoredRef.current = true
    el.scrollTop = memo0.pinned ? el.scrollHeight : memo0.scrollTop
  }, [visibleCount, memo0])

  // 只有用户停在底部时才跟随，往上翻看历史时不打扰
  useEffect(() => {
    const el = scrollRef.current
    if (!el || !pinnedRef.current || !restoredRef.current) return
    el.scrollTo({ top: el.scrollHeight, behavior: reduced ? 'auto' : 'smooth' })
  }, [visibleCount, reduced])

  const onDoneRef = useRef(onDone)
  useEffect(() => {
    onDoneRef.current = onDone
  }, [onDone])
  useEffect(() => {
    onDoneRef.current?.(done)
  }, [done])

  const lineById = useMemo(() => new Map(lines.map((l) => [l.id, l])), [lines])

  // 与书写同步：笔尖进入新的一行时通知外部
  const revealedRef = useRef<string | null>(null)
  const onRevealRef = useRef(onReveal)
  useEffect(() => {
    onRevealRef.current = onReveal
  }, [onReveal])
  useEffect(() => {
    const id = visibleCount > 0 ? chars[visibleCount - 1]?.lineId ?? null : null
    if (id === revealedRef.current) return
    revealedRef.current = id
    onRevealRef.current?.(id ? lineById.get(id) ?? null : null)
  }, [visibleCount, chars, lineById])

  // 行区间（chars 按行连续）：只在 chars 变化（新行到达）时算一次，逐帧只做二分查找，不再每帧从头分组
  const ranges = useMemo(() => {
    const out: { lineId: string; role: StreamLine['role']; start: number; end: number }[] = []
    chars.forEach((c, i) => {
      const cur = out[out.length - 1]
      if (!cur || cur.lineId !== c.lineId) out.push({ lineId: c.lineId, role: c.role, start: i, end: i + 1 })
      else cur.end = i + 1
    })
    return out
  }, [chars])
  let shownLines = 0
  for (let lo = 0, hi = ranges.length; lo < hi; ) {
    const mid = (lo + hi) >> 1
    if (ranges[mid].start < visibleCount) lo = shownLines = mid + 1
    else hi = mid
  }
  const grouped = ranges.slice(0, shownLines)

  // 记下本会话已显示到第几行（只增不减；重播时会被清零后重新累计）
  useEffect(() => {
    if (!sessionKey) return
    const prev = sessionMemo.get(sessionKey)
    sessionMemo.set(sessionKey, { lines: shownLines, scrollTop: prev?.scrollTop ?? 0, pinned: prev?.pinned ?? true })
  }, [sessionKey, shownLines])

  const lastRole = grouped[grouped.length - 1]?.role
  const activeRole =
    roleOverride !== undefined ? roleOverride : lastRole && lastRole !== 'system' ? lastRole : null
  const state: 'writing' | 'paused' | 'idle' | 'done' = done
    ? 'done'
    : !playing
      ? 'paused'
      : visibleCount < chars.length
        ? 'writing'
        : 'idle'
  const stateTip = {
    writing: t('落笔 · {0}', activeRole ? roleLabel[activeRole] : ''),
    paused: t('已暂停'),
    idle: t('等待下一行'),
    done: t('写毕'),
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
            label={done ? t('重播') : playing ? t('暂停') : t('继续')}
          >
            {done ? <RotateCcw size={13} strokeWidth={1.6} /> : playing ? <Pause size={13} strokeWidth={1.6} /> : <Play size={13} strokeWidth={1.6} />}
          </IconButton>
          {!done && (
            <IconButton onClick={handleRestart} label={t('从头')}>
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
          if (sessionKey && restoredRef.current) {
            const prev = sessionMemo.get(sessionKey)
            sessionMemo.set(sessionKey, { lines: prev?.lines ?? 0, scrollTop: el.scrollTop, pinned: pinnedRef.current })
          }
        }}
        className="stream-paper relative min-h-0 flex-1 overflow-y-auto scroll-soft px-5 py-5"
      >
        <div className="selectable font-mono text-[13px] leading-[1.85] text-ink-soft">
          {grouped.map((line, li) => {
            const isLast = li === grouped.length - 1
            const meta = lineById.get(line.lineId)
            // 最后两行逐字（墨迹还在沉淀）；更早的行墨已干，整行一个文本节点 + memo，长任务里 DOM 不再按字膨胀
            const live = !reduced && li >= grouped.length - 2
            const glyphs = live
              ? chars.slice(line.start, Math.min(line.end, visibleCount)).map((c) => (
                  <span key={c.key} className="ink-char">
                    {c.ch}
                  </span>
                ))
              : keepTokensTogether(meta?.text ?? chars.slice(line.start, line.end).map((c) => c.ch).join(''))
            return (
              <StreamLineView
                key={line.lineId}
                role={line.role}
                tone={meta?.tone ?? 'normal'}
                caret={isLast && !done ? (playing ? 'on' : 'rest') : 'off'}
              >
                {glyphs}
              </StreamLineView>
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
      className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-border-soft bg-panel-raised/80 text-sepia transition-colors duration-500 hover:border-amber-soft hover:text-amber-ink"
    >
      {children}
    </button>
    </Tip>
  )
}

/** 一行推流；墨干的行 children 是字符串，props 不变就不重渲染 */
const StreamLineView = memo(function StreamLineView({
  role,
  tone,
  caret,
  children,
}: {
  role: StreamLine['role']
  tone: NonNullable<StreamLine['tone']>
  caret: 'on' | 'rest' | 'off'
  children: ReactNode
}) {
  const caretEl = caret !== 'off' && <span className={clsx('caret-ink', caret === 'rest' && 'caret-rest')} aria-hidden />
  if (tone === 'chapter' || tone === 'divider') {
    return (
      <div className={clsx('stream-line stream-rule cv-line', tone === 'chapter' ? 'stream-chapter' : 'stream-divider')}>
        <span className="stream-rule-line" />
        <span className="stream-rule-text">
          {children}
          {caretEl}
        </span>
        <span className="stream-rule-line" />
      </div>
    )
  }
  return (
    <div className={clsx('stream-line cv-line relative mb-3 flex gap-3', `tone-${tone}`)}>
      <span className="relative mt-[0.62em] flex h-[7px] w-[7px] shrink-0">
        <span className="ink-bloom" style={{ background: `radial-gradient(circle, ${roleColor[role]}55, transparent 70%)` }} />
        <span className="role-dot" style={{ background: roleColor[role] }} />
      </span>
      <p className="min-w-0 flex-1 whitespace-pre-wrap break-words">
        <span
          className="mr-2 inline-block select-none font-sans text-[13px] font-medium tracking-[0.12em]"
          style={{ color: roleColor[role] }}
        >
          {roleLabel[role]}
        </span>
        {children}
        {caretEl}
      </p>
    </div>
  )
})

/**
 * 右栏断行（走查 r2-3）：这些片段整体不拆行
 * - 「(+18 −4)」增删统计
 * - 「test_issue_87.py → 1 failed」结果
 * - 「$ write_file <路径>」：路径不单独掉行，过长时中间省略，悬停看全路径
 */
const TOKEN_RE = /([(（]\+\d+ [−-]\d+[)）]|\S+ → \d+ [A-Za-z]+|\$ write_file \S+)/
function keepTokensTogether(text: string): ReactNode {
  const parts = text.split(TOKEN_RE)
  if (parts.length === 1) return text
  return parts.map((p, i) => {
    if (!(i % 2)) return p
    const m = /^(\$ write_file )(\S+)$/.exec(p) ?? /^(\S+)( → \d+ [A-Za-z]+)$/.exec(p)
    if (m) {
      const isWrite = m[1].startsWith('$')
      const path = isWrite ? m[2] : m[1]
      const pathEl = (
        <span key="p" title={path} data-testid="stream-path">
          {middlePath(path, 24)}
        </span>
      )
      return (
        <span key={i} className="whitespace-nowrap">
          {isWrite ? ['$ write_file\u00a0', pathEl] : [pathEl, m[2].replace(/ /g, '\u00a0')]}
        </span>
      )
    }
    return (
      <span key={i} className="whitespace-nowrap">
        {p}
      </span>
    )
  })
}

