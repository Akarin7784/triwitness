import { useEffect, useEffectEvent, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, CheckCircle2, CircleDashed, ExternalLink, Loader2, RefreshCw, ShieldCheck, XCircle } from 'lucide-react'
import clsx from 'clsx'
import { coreTool } from '../../lib/coreTool'
import { Btn, Dialog, DialogActions } from '../Dialog'
import { t as tr } from '../../lib/i18n'

type State = 'ok' | 'stopped' | 'missing' | 'n/a' | 'unknown'
interface Component {
  state: State
  detail: string
  version: string | null
}
interface Report {
  platform: string
  docker: Component
  wsl: Component
  winget: Component
  recommended: ('docker' | 'wsl')[]
  sandbox_ready: boolean
}
interface Plan {
  target: 'docker' | 'wsl'
  supported: boolean
  display: string
  needs_elevation: boolean
  reboot_hint: boolean
  note: string
  fallback_urls: string[]
}
interface InstallOut {
  ok: boolean
  exit_code: number
  output: string
  after: Report
}

const ICON: Record<State, { I: typeof CheckCircle2; cls: string; label: string }> = {
  ok: { I: CheckCircle2, cls: 'text-sage', label: tr('就绪') },
  stopped: { I: AlertTriangle, cls: 'text-amber-ink', label: tr('未运行') },
  missing: { I: XCircle, cls: 'text-rose-ink', label: tr('未安装') },
  'n/a': { I: CircleDashed, cls: 'text-sepia-muted', label: tr('不需要') },
  unknown: { I: CircleDashed, cls: 'text-sepia-muted', label: tr('未知') },
}
const STEPS = [tr('等待管理员确认（UAC）'), tr('下载并安装'), tr('重新检测')]

/**
 * UI-19：Docker / WSL2 检测与引导安装。只读检测随时可做；安装必须先看到命令、点“开始安装”，
 * 再由 Windows 弹出管理员确认（UAC）。从不自动安装。
 */
export function SandboxInstall() {
  const [report, setReport] = useState<Report | null>(null)
  const [checking, setChecking] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [plan, setPlan] = useState<Plan | null>(null)
  const [phase, setPhase] = useState<'confirm' | 'running' | 'done'>('confirm')
  const [step, setStep] = useState(0)
  const [outcome, setOutcome] = useState<{ ok: boolean; text: string } | null>(null)

  const apply = (r: Awaited<ReturnType<typeof coreTool<Report>>>) => {
    setChecking(false)
    if (r.ok) {
      setReport(r.data)
      setErr(null)
    } else setErr(r.error)
  }
  const detect = async () => {
    setChecking(true)
    apply(await coreTool<Report>(['doctor', '--json']))
  }
  const applyFirst = useEffectEvent(apply)
  useEffect(() => {
    let live = true
    void coreTool<Report>(['doctor', '--json']).then((r) => live && applyFirst(r))
    return () => {
      live = false
    }
  }, [])

  const ask = async (target: 'docker' | 'wsl') => {
    const r = await coreTool<Plan>(['sandbox', 'install', target, '--plan'])
    if (!r.ok) return setErr(r.error)
    setOutcome(null)
    setPhase('confirm')
    setStep(0)
    setPlan(r.data)
  }
  const install = async () => {
    if (!plan) return
    setPhase('running')
    setStep(0)
    const t = window.setTimeout(() => setStep(1), 2500)
    const r = await coreTool<InstallOut>(['sandbox', 'install', plan.target, '--yes'])
    window.clearTimeout(t)
    setStep(2)
    if (r.ok) {
      setReport(r.data.after)
      setOutcome({ ok: r.data.ok, text: r.data.ok ? (plan.reboot_hint ? tr('安装完成。按提示重启后再回来检测。') : tr('安装完成。')) : tr('安装未完成（退出码 {0}）。{1}', r.data.exit_code, r.data.output.slice(-300)) })
    } else {
      setOutcome({ ok: false, text: r.error })
      await detect()
    }
    setPhase('done')
  }

  const rows: { key: 'docker' | 'wsl' | 'winget'; name: string; hint: string }[] = [
    { key: 'docker', name: 'Docker', hint: tr('断网容器沙箱') },
    { key: 'wsl', name: 'WSL2', hint: tr('Docker Desktop 依赖它（Windows）') },
    { key: 'winget', name: 'winget', hint: tr('用于一键安装（Windows）') },
  ]

  return (
    <div data-testid="sandbox-install" className="py-2">
      <div className="flex items-center justify-between py-2">
        <p className={clsx('text-[12.5px]', report?.sandbox_ready ? 'text-sage' : 'text-sepia')}>
          {err ? <span className="text-rose-ink">{err}</span> : report ? (report.sandbox_ready ? tr('沙箱就绪') : tr('沙箱未就绪：任务会用本机工作树（无隔离）')) : tr('检测中…')}
        </p>
        <button type="button" data-testid="sandbox-detect" onClick={() => void detect()} disabled={checking} className="chip hover:text-amber-ink disabled:opacity-50">
          <RefreshCw size={11} className={clsx(checking && 'animate-spin')} /> {tr('重新检测')}
        </button>
      </div>
      <ul className="divide-y divide-border-soft/70">
        {rows.map((row) => {
          const c = report?.[row.key]
          const st = ICON[c?.state ?? 'unknown']
          const target = row.key === 'winget' ? null : row.key
          const canInstall = !!target && !!report && c?.state === 'missing'
          return (
            <li key={row.key} data-testid={`sandbox-${row.key}`} data-state={c?.state ?? 'unknown'} className="flex items-center gap-3 py-3">
              <motion.span key={c?.state} initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: 'spring', stiffness: 500, damping: 28 }}>
                {checking && !report ? <Loader2 size={16} className="animate-spin text-sepia-muted" /> : <st.I size={16} strokeWidth={1.7} className={st.cls} />}
              </motion.span>
              <span className="w-[76px] shrink-0 text-[13.5px] text-ink">{row.name}</span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[12.5px] text-ink-soft">{c ? c.detail : row.hint}</span>
                {c?.version && <span className="block font-mono text-[10.5px] text-sepia-muted">{c.version}</span>}
              </span>
              <span className={clsx('shrink-0 text-[11.5px]', st.cls)}>{c ? st.label : ''}</span>
              {canInstall && target && (
                <button type="button" data-testid={`install-${target}`} onClick={() => void ask(target)} className="chip shrink-0 border-amber/50 text-amber-ink hover:bg-amber/10">
                  {target === 'wsl' ? tr('启用') : tr('安装')}
                </button>
              )}
            </li>
          )
        })}
      </ul>

      <Dialog open={!!plan} onClose={() => phase !== 'running' && setPlan(null)} title={plan?.target === 'wsl' ? tr('启用 WSL2') : tr('安装 Docker Desktop')} width={520} testId="install-dialog">
        {plan && (
          <div>
            {!plan.supported ? (
              <>
                <p className="text-[13px] leading-relaxed text-ink-soft">{plan.note}</p>
                {plan.fallback_urls.length > 0 && <Links urls={plan.fallback_urls} />}
                <DialogActions>
                  <Btn kind="solid" onClick={() => setPlan(null)}>
                    {tr('知道了')}
                  </Btn>
                </DialogActions>
              </>
            ) : (
              <>
                <p className="text-[13px] leading-relaxed text-ink-soft">{tr('将以管理员身份运行：')}</p>
                <pre data-testid="install-command" className="selectable mt-2 whitespace-pre-wrap rounded-xl border border-border-soft bg-cream/70 px-3 py-2 font-mono text-[12px] text-ink">
                  {plan.display}
                </pre>
                <ul className="mt-3 space-y-1 text-[12.5px] text-sepia">
                  <li className="flex items-center gap-1.5">
                    <ShieldCheck size={13} className="text-amber-ink" /> {tr('Windows 会弹出管理员确认（UAC），你点“是”才会开始')}
                  </li>
                  {plan.reboot_hint && <li className="pl-[19px]">{plan.note}</li>}
                </ul>
                <AnimatePresence>
                  {phase !== 'confirm' && (
                    <motion.ol
                      data-testid="install-progress"
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      transition={{ type: 'spring', stiffness: 380, damping: 36 }}
                      className="mt-4 space-y-2 overflow-hidden"
                    >
                      {STEPS.map((s, i) => {
                        const done = phase === 'done' || i < step
                        const active = phase === 'running' && i === step
                        return (
                          <li key={s} className="flex items-center gap-2 text-[12.5px]">
                            {done ? <CheckCircle2 size={14} className="text-sage" /> : active ? <Loader2 size={14} className="animate-spin text-amber-ink" /> : <CircleDashed size={14} className="text-sepia-muted" />}
                            <span className={clsx(done || active ? 'text-ink' : 'text-sepia-muted')}>{s}</span>
                          </li>
                        )
                      })}
                      {phase === 'running' && (
                        <div className="relative mt-2 h-1 overflow-hidden rounded-full bg-border-soft">
                          <span className="indeterminate absolute inset-y-0 w-1/3 rounded-full bg-amber/70" />
                        </div>
                      )}
                    </motion.ol>
                  )}
                </AnimatePresence>
                {outcome && (
                  <p data-testid="install-outcome" className={clsx('mt-3 text-[12.5px] leading-relaxed', outcome.ok ? 'text-sage' : 'text-rose-ink')}>
                    {outcome.text}
                  </p>
                )}
                {outcome && !outcome.ok && plan.fallback_urls.length > 0 && <Links urls={plan.fallback_urls} />}
                <DialogActions>
                  {phase === 'confirm' && (
                    <>
                      <Btn onClick={() => setPlan(null)}>{tr('取消')}</Btn>
                      <Btn kind="solid" onClick={() => void install()} testId="install-start">
                        {tr('开始安装')}
                      </Btn>
                    </>
                  )}
                  {phase === 'running' && <Btn disabled>{tr('安装中…')}</Btn>}
                  {phase === 'done' && (
                    <Btn kind="solid" onClick={() => setPlan(null)}>
                      {tr('完成')}
                    </Btn>
                  )}
                </DialogActions>
              </>
            )}
          </div>
        )}
      </Dialog>
    </div>
  )
}

function Links({ urls }: { urls: string[] }) {
  return (
    <ul className="mt-3 space-y-1">
      {urls.map((u) => (
        <li key={u}>
          <a href={u} target="_blank" rel="noreferrer" className="inline-flex max-w-full items-center gap-1 truncate text-[12px] text-amber-ink underline decoration-amber/40 underline-offset-2">
            <ExternalLink size={11} className="shrink-0" /> <span className="truncate">{u}</span>
          </a>
        </li>
      ))}
    </ul>
  )
}
