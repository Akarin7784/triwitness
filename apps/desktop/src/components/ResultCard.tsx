import { useState } from 'react'
import { ChevronDown, ScrollText } from 'lucide-react'
import clsx from 'clsx'
import type { ResultMsg } from '../bridge/protocol'
import { prSummary } from '../bridge/liveTask'
import { t } from '../lib/i18n'

const VERDICT: Record<string, { label: string; cls: string }> = {
  pass: { label: t('复验通过'), cls: 'bg-sage/14 text-sage' },
  fail: { label: t('复验未过'), cls: 'bg-rose-ink/12 text-rose-ink' },
  inconclusive: { label: t('证据不足'), cls: 'bg-amber/14 text-amber' },
}

const STATUS: Record<string, string> = {
  done: t('已完成'),
  failed: t('未完成'),
  stuck: t('卡住'),
  budget_exceeded: t('超预算'),
  cancelled: t('已停止'),
  error: t('出错'),
}

/** 任务结尾的结论卡（UI-10，最小版）：裁决 · 风险 · PR 摘要；完整证据页后续做 */
export function ResultCard({ result }: { result: ResultMsg }) {
  const [open, setOpen] = useState(false)
  const v = result.verdict ? VERDICT[result.verdict] : null
  const lines = prSummary(result.pr_md, open ? 200 : 6)
  return (
    <article data-testid="result-card" className="paper-card fade-in mr-auto w-full max-w-[720px] rounded-2xl px-5 py-4">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={clsx(
            'inline-flex items-center rounded-full px-3 py-0.5 font-serif text-[15px] font-medium',
            v?.cls ?? 'bg-border-soft text-sepia',
          )}
        >
          {v?.label ?? STATUS[result.status] ?? result.status}
        </span>
        {result.risk_level && <span className="chip">{t('风险 {0}', result.risk_level)}</span>}
        {result.clean_env === 'verified' && <span className="chip">{t('干净环境')}</span>}
        <span className="chip ml-auto tabular-nums">{t('¥{0} · {1} 步', result.cost_cny.toFixed(3), result.steps)}</span>
      </div>
      {result.summary && <p className="selectable mt-3 text-[14px] leading-[1.8] text-ink-soft">{result.summary}</p>}
      {result.reason && !result.summary && (
        <p className="selectable mt-3 text-[13px] leading-[1.8] text-sepia">{result.reason}</p>
      )}
      {lines.length > 0 && (
        <div className="mt-3 border-t border-border-soft pt-3">
          <div className="mb-1.5 flex items-center gap-1.5 text-[11px] tracking-[0.12em] text-sepia-muted">
            <ScrollText size={12} strokeWidth={1.6} />
            pr.md
          </div>
          <pre className="selectable whitespace-pre-wrap font-mono text-[12px] leading-relaxed text-ink-soft">
            {lines.join('\n')}
          </pre>
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            className="mt-1 inline-flex items-center gap-1 text-[11.5px] text-sepia-muted transition-colors hover:text-amber"
          >
            <ChevronDown size={12} className={clsx('transition-transform', open && 'rotate-180')} />
            {open ? t('收起') : t('全文')}
          </button>
        </div>
      )}
      {result.branch && <p className="mt-2 font-mono text-[11px] text-sepia-muted">{result.branch}</p>}
    </article>
  )
}
