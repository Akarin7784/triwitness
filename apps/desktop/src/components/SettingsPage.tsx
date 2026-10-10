import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, ArrowRight, Ban, Check, Clock, Feather, Info, KeyRound, Lock, Wallet } from 'lucide-react'
import { Tip } from './Tip'
import clsx from 'clsx'
import {
  BUDGET_TOTAL,
  PEAK_WINDOWS,
  PRICE,
  TASK_CAP,
  beijingNow,
  gateStatus,
  ledger,
  rowCost,
} from '../data/budget'
import { coreMode, setCoreMode } from '../bridge/liveStore'
import type { CoreMode } from '../bridge/protocol'

const WEEK = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

function useNow(ms = 30_000) {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const t = window.setInterval(() => setNow(new Date()), ms)
    return () => window.clearInterval(t)
  }, [ms])
  return now
}

export function SettingsPage({ onBack }: { onBack: () => void }) {
  const now = useNow()
  const bj = beijingNow(now)
  const gate = gateStatus(now)
  const spent = useMemo(() => ledger.reduce((s, r) => s + rowCost(r), 0), [])
  const hhmm = `${String(bj.hh).padStart(2, '0')}:${String(bj.mm).padStart(2, '0')}`

  return (
    <section className="fade-in min-w-0 flex-1 overflow-y-auto scroll-soft">
      <div className="mx-auto max-w-[880px] px-10 pb-16 pt-7">
        <div className="flex items-center gap-3">
          <Tip label="返回" side="bottom">
            <button type="button" onClick={onBack} aria-label="返回" className="tb-icon">
              <ArrowLeft size={15} strokeWidth={1.5} />
            </button>
          </Tip>
          <h1 className="font-serif text-[26px] font-semibold tracking-wide text-ink">设置</h1>
        </div>

        <Section icon={<Lock size={14} strokeWidth={1.6} />} title="模型">
          <div className="grid gap-3 sm:grid-cols-2">
            <ModelCard name="deepseek-flash" state="allowed">
              <span className="chip">执行 · 非思考</span>
              <span className="chip">评审 · 思考</span>
            </ModelCard>
            <ModelCard name="deepseek-v4-pro" state="banned" tip="更贵，且不如 v4.1 Flash" />
            <ModelCard name="qwen · glm" state="later" tip="跨厂商评审" />
            <div className="paper-card flex items-center justify-between rounded-2xl p-4">
              <span className="flex items-center gap-2.5 text-[13px] text-ink-soft">
                <KeyRound size={14} strokeWidth={1.6} className="text-sepia" />
                API 密钥
              </span>
              <Tip label="系统凭据库 · 不显示明文" side="top-end">
                <span className="inline-flex items-center gap-1 rounded-full bg-sage/15 px-2 py-0.5 text-[10.5px] text-sage">
                  <Lock size={10} strokeWidth={2} /> 已托管
                </span>
              </Tip>
            </div>
          </div>
        </Section>

        <Section icon={<Feather size={14} strokeWidth={1.6} />} title="运行方式">
          <CoreModePicker />
        </Section>

        <Section icon={<Clock size={14} strokeWidth={1.6} />} title="高峰闸门">
          <div className="paper-card rounded-2xl p-5">
            <div className="flex flex-wrap items-center gap-3">
              <span
                className={clsx(
                  'inline-flex items-center gap-2 rounded-full px-3.5 py-1 font-serif text-[16px] font-medium',
                  gate.inPeak ? 'bg-rose-ink/12 text-rose-ink' : 'bg-sage/14 text-sage',
                )}
              >
                <span className={clsx('pulse-dot h-2 w-2 rounded-full', gate.inPeak ? 'bg-rose-ink' : 'bg-sage')} />
                {gate.inPeak ? '高峰' : '空闲'}
              </span>
              <Tip label="北京时间" side="bottom">
                <span className="font-mono text-[13px] tabular-nums text-ink-soft">
                  {WEEK[bj.day]} {hhmm}
                </span>
              </Tip>
              <Tip label="下次切换" side="bottom">
                <span className="chip">
                  <ArrowRight size={11} strokeWidth={1.7} />
                  {gate.nextShort}
                </span>
              </Tip>
            </div>

            <DayBar minutes={bj.minutes} weekday={gate.weekday} />
            <WeekGrid today={bj.day} />
          </div>
        </Section>

        <Section icon={<Wallet size={14} strokeWidth={1.6} />} title="预算">
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat label="单任务上限" value={`¥${TASK_CAP.toFixed(2)}`} tip="超出即中止" />
            <Stat label="总预算" value={`¥${BUDGET_TOTAL}`} tip="花完自动停" />
            <Stat label="已花费" value={`¥${spent.toFixed(2)}`} tip={`余 ¥${(BUDGET_TOTAL - spent).toFixed(2)}`} />
          </div>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-border-soft">
            <div className="h-full rounded-full bg-amber/70" style={{ width: `${Math.max(1.5, (spent / BUDGET_TOTAL) * 100)}%` }} />
          </div>

          <div className="paper-card mt-5 overflow-hidden rounded-2xl">
            <div className="flex items-center gap-2 px-5 py-3">
              <p className="font-serif text-[14px] text-ink-soft">账本</p>
              <Tip
                label={`空闲价 · 命中 ${PRICE.idle.hit} / 未命中 ${PRICE.idle.miss} / 输出 ${PRICE.idle.out} 元每百万 token`}
                side="right"
              >
                <Info size={12} strokeWidth={1.6} className="text-sepia-muted" />
              </Tip>
            </div>
            <table className="w-full text-left text-[12px]">
              <thead className="border-y border-border-soft bg-parchment/60 text-[10.5px] tracking-wide text-sepia-muted">
                <tr>
                  <th className="px-5 py-2 font-normal">时间</th>
                  <th className="px-2 py-2 font-normal">任务</th>
                  <th className="px-2 py-2 font-normal">模式</th>
                  <th className="px-2 py-2 text-right font-normal">命中率</th>
                  <th className="px-2 py-2 text-right font-normal">token</th>
                  <th className="px-5 py-2 text-right font-normal">花费</th>
                </tr>
              </thead>
              <tbody className="selectable text-ink-soft">
                {ledger.map((r) => {
                  const total = r.hitM + r.missM
                  const c = rowCost(r)
                  return (
                    <tr key={r.id} className="border-b border-border-soft/70 transition-colors duration-300 last:border-0 hover:bg-parchment/50">
                      <td className="px-5 py-2.5 font-mono text-[11px] text-sepia">{r.when}</td>
                      <td className="px-2 py-2.5">{r.task}</td>
                      <td className="px-2 py-2.5 text-sepia">{r.mode}</td>
                      <td className="px-2 py-2.5 text-right tabular-nums">{((r.hitM / total) * 100).toFixed(0)}%</td>
                      <td className="px-2 py-2.5 text-right font-mono text-[11px] tabular-nums text-sepia">
                        {(total + r.outM).toFixed(2)}M
                      </td>
                      <td className={clsx('px-5 py-2.5 text-right tabular-nums', c > TASK_CAP && 'text-rose-ink')}>
                        ¥{c.toFixed(2)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Section>
      </div>
    </section>
  )
}

const MODES: { id: CoreMode; label: string; tip: string }[] = [
  { id: 'demo', label: '演示', tip: '脚本模型 · 示例仓库 · ¥0' },
  { id: 'replay', label: '回放', tip: '用录好的模型回复 · ¥0' },
  { id: 'live', label: '真实', tip: 'deepseek-flash · 计费 · 受高峰闸门约束' },
]

function CoreModePicker() {
  const [mode, setMode] = useState<CoreMode>(coreMode)
  return (
    <div data-testid="core-mode" className="paper-card inline-flex rounded-full p-1">
      {MODES.map((m) => (
        <Tip key={m.id} label={m.tip} side="bottom">
          <button
            type="button"
            onClick={() => {
              setCoreMode(m.id)
              setMode(m.id)
            }}
            className={clsx(
              'rounded-full px-4 py-1 text-[13px] transition-colors duration-300',
              mode === m.id ? 'bg-ink text-parchment' : 'text-ink-soft hover:text-amber',
            )}
          >
            {m.label}
          </button>
        </Tip>
      ))}
    </div>
  )
}

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="mt-9">
      <div className="mb-3 flex items-center gap-2.5">
        <span className="text-amber">{icon}</span>
        <h2 className="font-serif text-[17px] font-medium text-ink">{title}</h2>
      </div>
      {children}
    </div>
  )
}

function ModelCard({
  name,
  state,
  tip,
  children,
}: {
  name: string
  state: 'allowed' | 'banned' | 'later'
  tip?: string
  children?: React.ReactNode
}) {
  const badge =
    state === 'allowed' ? (
      <span className="inline-flex items-center gap-1 rounded-full bg-sage/15 px-2 py-0.5 text-[10.5px] text-sage">
        <Check size={11} strokeWidth={2} /> 启用
      </span>
    ) : state === 'banned' ? (
      <span className="inline-flex items-center gap-1 rounded-full bg-rose-ink/12 px-2 py-0.5 text-[10.5px] text-rose-ink">
        <Ban size={11} strokeWidth={2} /> 禁用
      </span>
    ) : (
      <span className="rounded-full bg-border-soft px-2 py-0.5 text-[10.5px] text-sepia">以后</span>
    )
  return (
    <div className={clsx('paper-card rounded-2xl p-4', state !== 'allowed' && 'opacity-70')}>
      <div className="flex items-center justify-between gap-2">
        <p
          className={clsx(
            'font-mono text-[13px]',
            state === 'banned' ? 'text-sepia line-through decoration-rose-ink/60' : 'text-ink',
          )}
        >
          {name}
        </p>
        {tip ? (
          <Tip label={tip} side="top-end">
            {badge}
          </Tip>
        ) : (
          badge
        )}
      </div>
      {children && <div className="mt-3 flex flex-wrap gap-1.5">{children}</div>}
    </div>
  )
}

function Stat({ label, value, tip }: { label: string; value: string; tip: string }) {
  return (
    <Tip label={tip} side="bottom" className="block">
      <div className="paper-card w-full rounded-2xl p-4">
        <p className="text-[11px] text-sepia-muted">{label}</p>
        <p className="mt-1 font-serif text-[24px] font-medium tabular-nums text-ink">{value}</p>
      </div>
    </Tip>
  )
}

function DayBar({ minutes, weekday }: { minutes: number; weekday: boolean }) {
  return (
    <div className="mt-6">
      <div className="relative h-7 overflow-hidden rounded-lg bg-sage/18">
        {PEAK_WINDOWS.map(([a, b]) => (
          <div
            key={a}
            className={clsx(
              'absolute inset-y-0',
              weekday ? 'bg-rose-ink/35' : 'border-x border-dashed border-rose-ink/40 bg-rose-ink/[0.06]',
            )}
            style={{ left: `${(a / 24) * 100}%`, width: `${((b - a) / 24) * 100}%` }}
          />
        ))}
        <div className="absolute inset-y-0 w-[2px] bg-ink" style={{ left: `${(minutes / 1440) * 100}%` }}>
          <span className="absolute -top-0.5 left-1/2 h-1.5 w-1.5 -translate-x-1/2 rounded-full bg-ink" />
        </div>
      </div>
      <div className="relative mt-1.5 h-3 font-mono text-[9.5px] text-sepia-muted">
        {[0, 6, 9, 12, 14, 18, 24].map((h) => (
          <span key={h} className="absolute -translate-x-1/2" style={{ left: `${(h / 24) * 100}%` }}>
            {String(h).padStart(2, '0')}
          </span>
        ))}
      </div>
      <p className="mt-2 flex items-center gap-3 text-[10.5px] text-sepia-muted">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-3 rounded-sm bg-rose-ink/35" />
          高峰
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-3 rounded-sm bg-sage/25" />
          空闲
        </span>
      </p>
    </div>
  )
}

function WeekGrid({ today }: { today: number }) {
  const order = [1, 2, 3, 4, 5, 6, 0]
  return (
    <div className="mt-5 grid grid-cols-7 gap-1.5">
      {order.map((d) => {
        const weekday = d >= 1 && d <= 5
        return (
          <div key={d} className="text-center">
            <p className={clsx('mb-1 text-[10.5px]', d === today ? 'font-medium text-ink' : 'text-sepia-muted')}>{WEEK[d]}</p>
            <div className={clsx('relative h-10 overflow-hidden rounded-md bg-sage/18', d === today && 'ring-1 ring-ink/40')}>
              {weekday &&
                PEAK_WINDOWS.map(([a, b]) => (
                  <div
                    key={a}
                    className="absolute inset-x-0 bg-rose-ink/35"
                    style={{ top: `${(a / 24) * 100}%`, height: `${((b - a) / 24) * 100}%` }}
                  />
                ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
