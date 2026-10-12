import { useState } from 'react'
import { ShieldQuestion } from 'lucide-react'
import clsx from 'clsx'
import type { PendingApproval } from '../bridge/liveTask'
import type { ApprovalScope } from '../bridge/protocol'
import { Tip } from './Tip'
import { toast } from '../lib/toast'
import { t } from '../lib/i18n'

type Choice = { decision: 'allow' | 'deny'; scope: ApprovalScope }

const CHOICES: { label: string; tip: string; choice: Choice; tone?: 'primary' | 'deny' }[] = [
  { label: t('允许一次'), tip: t('只这一次'), choice: { decision: 'allow', scope: 'once' }, tone: 'primary' },
  { label: t('本次任务'), tip: t('本任务内同类不再问'), choice: { decision: 'allow', scope: 'session' } },
  { label: t('总是'), tip: t('写入本机规则'), choice: { decision: 'allow', scope: 'always' } },
  { label: t('拒绝'), tip: t('执行方会换条路'), choice: { decision: 'deny', scope: 'once' }, tone: 'deny' },
]

/** 权限审批卡（UI-10）：核心在等，四个选择回传给 tw-bridge/1 */
export function ApprovalCard({
  req,
  onDecide,
}: {
  req: PendingApproval
  onDecide: (c: Choice) => Promise<void>
}) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const decide = async (c: Choice) => {
    setBusy(true)
    setErr(null)
    try {
      await onDecide(c)
      if (c.scope === 'always') toast(t('已写入此仓库规则{0} · 设置 → 权限可编辑', req.suggestedRule ? t('：{0}', req.suggestedRule) : ''))
    } catch (e) {
      setErr(String(e instanceof Error ? e.message : e))
      setBusy(false)
    }
  }
  return (
    <article data-testid="approval-card" className="paper-card fade-in mr-auto max-w-[68em] rounded-2xl border-amber/40 px-4 py-3.5">
      <div className="flex items-center gap-2 text-[13px] text-amber-ink">
        <ShieldQuestion size={14} strokeWidth={1.7} />
        <span className="tracking-[0.12em]">{t('待批')}</span>
        <span className="text-sepia-muted">· {req.tool}</span>
        {req.risk && <span className="chip ml-auto">{req.risk}</span>}
      </div>
      <p className="selectable mt-2 break-all font-mono text-[13px] leading-relaxed text-ink">{req.action}</p>
      {req.reason && <p className="mt-1 text-[13px] text-sepia-muted">{req.reason}</p>}
      <div className="mt-3 flex flex-wrap gap-2">
        {CHOICES.map((c) => (
          <Tip key={c.label} label={c.choice.scope === 'always' && req.suggestedRule ? t('写入规则 {0}', req.suggestedRule) : c.tip}>
            <button
              type="button"
              disabled={busy}
              onClick={() => decide(c.choice)}
              className={clsx(
                'rounded-full px-3.5 py-1 text-[13px] transition-colors duration-300 disabled:opacity-40',
                c.tone === 'primary'
                  ? 'bg-ink text-parchment enabled:hover:bg-espresso'
                  : c.tone === 'deny'
                    ? 'border border-rose-ink/30 text-rose-ink enabled:hover:bg-rose-ink/8'
                    : 'border border-border text-ink-soft enabled:hover:bg-panel-raised',
              )}
            >
              {c.label}
            </button>
          </Tip>
        ))}
      </div>
      {err && <p className="mt-2 text-[13px] text-rose-ink">{err}</p>}
    </article>
  )
}
