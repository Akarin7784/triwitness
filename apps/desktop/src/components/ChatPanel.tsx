import { useEffect, useRef } from 'react'
import { FolderGit2 } from 'lucide-react'
import clsx from 'clsx'
import type { ChatMessage } from '../types'
import { cacheHitRate, type RunView } from '../data/mapEvent'
import { MessageBubble } from './MessageBubble'
import { Composer } from './Composer'
import { Tip } from './Tip'
import { PHASE_DOT } from './phase'

interface ChatPanelProps {
  title: string
  run: RunView | null
  messages: ChatMessage[]
  onSend: (text: string) => void
}

export function ChatPanel({ title, run, messages, onSend }: ChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length])

  return (
    <section className="flex min-w-0 flex-1 flex-col">
      <header className="flex items-center justify-between gap-4 px-8 pb-3 pt-5">
        <h2 className="min-w-0 truncate font-serif text-[20px] font-medium tracking-wide text-ink">{title}</h2>
        {run && (
          <div className="flex shrink-0 items-center gap-2">
            {run.repo && (
              <Tip label="仓库" side="bottom">
                <span className="chip">
                  <FolderGit2 size={11} strokeWidth={1.7} />
                  {run.repo}
                </span>
              </Tip>
            )}
            <CostChip run={run} />
            {run.label && (
              <span className="chip fade-in" key={run.label} data-testid="state-chip">
                <span className={clsx('h-1.5 w-1.5 rounded-full transition-colors duration-700', PHASE_DOT[run.phase])} />
                {run.label}
              </span>
            )}
          </div>
        )}
      </header>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto scroll-soft px-8 py-5">
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        <div ref={bottomRef} />
      </div>

      <Composer onSend={onSend} />
    </section>
  )
}

function CostChip({ run }: { run: RunView }) {
  const hit = cacheHitRate(run)
  const ratio = run.budgetCny > 0 ? run.costCny / run.budgetCny : 0
  const tip = [
    hit !== null ? `命中 ${Math.round(hit * 100)}%` : null,
    `上限 ¥${run.budgetCny.toFixed(2)}`,
    run.peakCalls ? `高峰 ${run.peakCalls} 次` : null,
  ]
    .filter(Boolean)
    .join(' · ')
  return (
    <Tip label={tip} side="bottom">
      <span
        data-testid="cost-chip"
        className={clsx(
          'chip tabular-nums transition-colors duration-700',
          ratio > 1 || run.phase === 'budget'
            ? 'border-rose-ink/40 text-rose-ink'
            : ratio > 0.8 || run.peakCalls > 0
              ? 'border-amber/50 text-amber'
              : '',
        )}
      >
        ¥{run.costCny.toFixed(3)}
        <span className="relative h-1 w-8 overflow-hidden rounded-full bg-border-soft">
          <span
            className={clsx(
              'absolute inset-y-0 left-0 rounded-full transition-[width] duration-700',
              ratio > 1 ? 'bg-rose-ink/70' : 'bg-amber/70',
            )}
            style={{ width: `${Math.min(100, ratio * 100)}%` }}
          />
        </span>
      </span>
    </Tip>
  )
}
