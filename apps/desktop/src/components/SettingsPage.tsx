import { useEffect, useId, useMemo, useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  ArrowLeft,
  ArrowRight,
  Box,
  Check,
  Info,
  KeyRound,
  Keyboard,
  Lock,
  Plug,
  Shield,
  ShieldAlert,
  SlidersHorizontal,
  Sparkles,
  UserRound,
  Wallet,
  EyeOff,
} from 'lucide-react'
import clsx from 'clsx'
import { Tip } from './Tip'
import { UnrestrictedDialog } from './ChatDialogs'
import { RulesEditor } from './settings/RulesEditor'
import { SandboxInstall } from './settings/SandboxInstall'
import { ClearHistoryDialog, LicensesDialog } from './settings/DataDialogs'
import { clearHistory, collectLocalData, exportFileStamp } from '../lib/localData'
import { saveText } from '../lib/download'
import {
  BUDGET_TOTAL,
  PEAK_WINDOWS,
  PRICE,
  beijingNow,
  gateStatus,
  ledger,
  rowCost,
} from '../data/budget'
import { coreMode, setCoreMode } from '../bridge/liveStore'
import type { CoreMode } from '../bridge/protocol'
import { MAX_COST_CAP, type Backend } from '../bridge/choices'
import {
  FONT_SCALES,
  MODELS,
  THINKING_LEVELS,
  armUnrestricted,
  disarmUnrestricted,
  setPrefs,
  usePrefs,
  useUnrestrictedArmed,
  type ChatFont,
  type Language,
  type SavedMode,
  type Theme,
} from '../lib/prefs'
import { secretClear, secretSet, secretStatus, type SecretState } from '../lib/secrets'
import { notYet, toast } from '../lib/toast'
import { parseRules, type RuleKind } from '../data/rules'
import defaultRulesYaml from '../../../../configs/permissions.default.yaml?raw'
import { t as tr } from '../lib/i18n'

const WEEK = [tr('周日'), tr('周一'), tr('周二'), tr('周三'), tr('周四'), tr('周五'), tr('周六')]
const VERSION = '0.2.1'

export type SettingsSection =
  | 'general'
  | 'profile'
  | 'model'
  | 'budget'
  | 'permissions'
  | 'sandbox'
  | 'connectors'
  | 'privacy'
  | 'about'

const SETTINGS_SECTIONS: { id: SettingsSection; label: string; icon: typeof Info }[] = [
  { id: 'general', label: tr('常规'), icon: SlidersHorizontal },
  { id: 'profile', label: tr('个人资料'), icon: UserRound },
  { id: 'model', label: tr('模型'), icon: Sparkles },
  { id: 'budget', label: tr('预算'), icon: Wallet },
  { id: 'permissions', label: tr('权限'), icon: Shield },
  { id: 'sandbox', label: tr('沙箱'), icon: Box },
  { id: 'connectors', label: tr('连接器'), icon: Plug },
  { id: 'privacy', label: tr('隐私'), icon: EyeOff },
  { id: 'about', label: tr('关于'), icon: Info },
]

function useNow(ms = 30_000) {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const t = window.setInterval(() => setNow(new Date()), ms)
    return () => window.clearInterval(t)
  }, [ms])
  return now
}

/** Claude 式设置：左侧分区导航，右侧一次一个分区；改动即时保存 */
export function SettingsPage({
  section,
  onSection,
  onBack,
  onShortcuts,
}: {
  section: SettingsSection
  onSection: (s: SettingsSection) => void
  onBack: () => void
  onShortcuts: () => void
}) {
  return (
    <section data-testid="settings" className="fade-in flex min-w-0 flex-1 overflow-hidden">
      <nav className="w-[208px] shrink-0 overflow-y-auto scroll-soft px-3 pb-6 pt-6">
        <div className="mb-4 flex items-center gap-2 px-2">
          <Tip label={tr('返回')} side="bottom">
            <button type="button" onClick={onBack} aria-label={tr('返回')} className="tb-icon">
              <ArrowLeft size={15} strokeWidth={1.5} />
            </button>
          </Tip>
          <h1 className="font-serif text-[20px] font-semibold tracking-wide text-ink">{tr('设置')}</h1>
        </div>
        {SETTINGS_SECTIONS.map((s) => (
          <button
            key={s.id}
            type="button"
            data-testid={`settings-nav-${s.id}`}
            onClick={() => onSection(s.id)}
            className={clsx(
              'relative flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-[13px] transition-colors duration-300',
              section === s.id ? 'text-ink' : 'text-ink-soft/85 hover:bg-panel-raised/60',
            )}
          >
            {section === s.id && (
              <motion.span
                layoutId="settings-nav-active"
                className="absolute inset-0 rounded-lg bg-panel-raised shadow-[0_1px_0_color-mix(in_srgb,var(--color-border)_60%,transparent)]"
                transition={{ type: 'spring', stiffness: 460, damping: 38 }}
              />
            )}
            <s.icon size={14} strokeWidth={1.6} className="relative text-sepia" />
            <span className="relative">{s.label}</span>
          </button>
        ))}
      </nav>
      <div className="min-w-0 flex-1 overflow-y-auto scroll-soft">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={section}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ pointerEvents: 'none', opacity: 0, y: -4, transition: { duration: 0.12 } }}
            transition={{ type: 'spring', stiffness: 380, damping: 34 }}
            className="max-w-[760px] px-12 pb-16 pt-8"
          >
            {section === 'general' && <General />}
            {section === 'profile' && <Profile />}
            {section === 'model' && <ModelSection />}
            {section === 'budget' && <Budget />}
            {section === 'permissions' && <Permissions />}
            {section === 'sandbox' && <Sandbox />}
            {section === 'connectors' && <Connectors />}
            {section === 'privacy' && <Privacy />}
            {section === 'about' && <About onShortcuts={onShortcuts} />}
          </motion.div>
        </AnimatePresence>
      </div>
    </section>
  )
}

/* ---------------------------------------------------------------- 通用小件 */

function Title({ children }: { children: ReactNode }) {
  return <h2 className="chapter-title mb-6 font-serif text-[22px] font-medium tracking-wide text-ink">{children}</h2>
}

function Row({ label, hint, children, testId }: { label: string; hint?: string; children: ReactNode; testId?: string }) {
  return (
    <div data-testid={testId} className="flex flex-wrap items-center justify-between gap-4 border-b border-border-soft/70 py-4 last:border-0">
      <div className="min-w-0">
        <p className="text-[13.5px] text-ink">{label}</p>
        {hint && <p className="mt-0.5 text-[11.5px] text-sepia-muted">{hint}</p>}
      </div>
      <div className="flex shrink-0 items-center gap-2">{children}</div>
    </div>
  )
}

function Group({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <div className="mb-7">
      {title && <p className="mb-2 text-[10.5px] tracking-[0.14em] text-sepia-muted">{title}</p>}
      <div className="paper-card rounded-2xl px-5">{children}</div>
    </div>
  )
}

function Segmented<T extends string | number>({
  value,
  options,
  onChange,
  testId,
}: {
  value: T
  options: { id: T; label: string; disabled?: boolean; tip?: string }[]
  onChange: (v: T) => void
  testId?: string
}) {
  const group = useId()
  return (
    <div data-testid={testId} className="relative inline-flex shrink-0 rounded-full bg-parchment-deep/70 p-1">
      {options.map((o) => {
        const btn = (
          <button
            key={String(o.id)}
            type="button"
            disabled={o.disabled}
            aria-pressed={value === o.id}
            onClick={() => (o.disabled ? undefined : onChange(o.id))}
            className={clsx(
              'relative whitespace-nowrap rounded-full px-3.5 py-1 text-[12.5px] transition-colors duration-300 disabled:cursor-not-allowed disabled:opacity-40',
              value === o.id ? 'text-parchment' : 'text-ink-soft hover:text-amber-ink',
            )}
          >
            {value === o.id && (
              <motion.span
                layoutId={`seg-${group}`}
                className="absolute inset-0 rounded-full bg-ink"
                transition={{ type: 'spring', stiffness: 520, damping: 38 }}
              />
            )}
            <span className="relative">{o.label}</span>
          </button>
        )
        return o.tip ? (
          <Tip key={String(o.id)} label={o.tip} side="bottom">
            {btn}
          </Tip>
        ) : (
          btn
        )
      })}
    </div>
  )
}

function Toggle({ on, onChange, danger, testId }: { on: boolean; onChange: (v: boolean) => void; danger?: boolean; testId?: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      data-testid={testId}
      onClick={() => onChange(!on)}
      className={clsx(
        'relative h-[22px] w-[38px] rounded-full transition-colors duration-300',
        on ? (danger ? 'bg-rose-ink' : 'bg-sage') : 'bg-border',
      )}
    >
      <motion.span
        layout
        transition={{ type: 'spring', stiffness: 700, damping: 34 }}
        className={clsx('absolute top-[3px] h-4 w-4 rounded-full bg-cream shadow', on ? 'right-[3px]' : 'left-[3px]')}
      />
    </button>
  )
}

const FIELD =
  'w-full rounded-xl border border-border-soft bg-cream/70 px-3 py-2 text-[13.5px] text-ink outline-none transition-colors duration-300 placeholder:text-sepia-muted/70 focus:border-amber/60'

/* ---------------------------------------------------------------- 常规 */

const THEMES: { id: Theme; label: string }[] = [
  { id: 'light', label: tr('浅色') },
  { id: 'auto', label: tr('跟随系统') },
  { id: 'dark', label: tr('深色') },
]

function ThemeSwatch({ id, active, onClick }: { id: Theme; active: boolean; onClick: () => void }) {
  const light = (
    <span className="flex h-full w-full flex-col gap-1 bg-[#f1e6d0] p-2">
      <span className="h-1.5 w-8 rounded-full bg-[#221812]/70" />
      <span className="h-1.5 w-12 rounded-full bg-[#2f4a72]/60" />
      <span className="mt-auto h-3 rounded-md bg-[#f8f0df] ring-1 ring-[#dccdb0]" />
    </span>
  )
  const dark = (
    <span className="flex h-full w-full flex-col gap-1 bg-[#211913] p-2">
      <span className="h-1.5 w-8 rounded-full bg-[#ecdfca]/70" />
      <span className="h-1.5 w-12 rounded-full bg-[#93acd6]/60" />
      <span className="mt-auto h-3 rounded-md bg-[#2b2119] ring-1 ring-[#3b3027]" />
    </span>
  )
  return (
    <button type="button" onClick={onClick} data-testid={`theme-${id}`} aria-pressed={active} className="group text-center">
      <span
        className={clsx(
          'block h-[68px] w-[104px] overflow-hidden rounded-xl ring-1 transition-all duration-300',
          active ? 'ring-2 ring-amber' : 'ring-border-soft group-hover:ring-border',
        )}
      >
        {id === 'light' ? light : id === 'dark' ? dark : (
          <span className="flex h-full w-full">
            <span className="w-1/2 overflow-hidden">{light}</span>
            <span className="w-1/2 overflow-hidden">{dark}</span>
          </span>
        )}
      </span>
      <span className={clsx('mt-1.5 block text-[12px]', active ? 'text-ink' : 'text-sepia')}>
        {THEMES.find((t) => t.id === id)!.label}
      </span>
    </button>
  )
}

function General() {
  const p = usePrefs()
  return (
    <>
      <Title>{tr('常规')}</Title>
      <Group title={tr('外观')}>
        <div className="flex gap-4 border-b border-border-soft/70 py-5">
          {THEMES.map((t) => (
            <ThemeSwatch key={t.id} id={t.id} active={p.theme === t.id} onClick={() => setPrefs({ theme: t.id })} />
          ))}
        </div>
        <Row label={tr('对话字体')}>
          <Segmented<ChatFont>
            value={p.chatFont}
            onChange={(chatFont) => setPrefs({ chatFont })}
            options={[
              { id: 'serif', label: tr('宋体') },
              { id: 'sans', label: tr('黑体') },
              { id: 'system', label: tr('系统') },
            ]}
            testId="chat-font"
          />
        </Row>
        <Row label={tr('字号')}>
          <Segmented<number>
            value={p.fontScale}
            onChange={(fontScale) => setPrefs({ fontScale })}
            options={FONT_SCALES.map((s) => ({ id: s, label: ({ 0.9: tr('小'), 1: tr('默认'), 1.1: tr('大'), 1.2: tr('特大') } as Record<number, string>)[s] }))}
            testId="font-scale"
          />
        </Row>
      </Group>
      <Group title={tr('语言')}>
        <Row label={tr('界面语言')}>
          <Segmented<Language>
            value={p.language}
            onChange={(language) => {
              if (language === p.language) return
              setPrefs({ language })
              window.setTimeout(() => window.location.reload(), 120)
            }}
            options={[
              { id: 'zh', label: tr('简体中文') },
              { id: 'en', label: 'English' },
            ]}
            testId="language"
          />
        </Row>
      </Group>
    </>
  )
}

/* ---------------------------------------------------------------- 个人资料 */

function Profile() {
  const p = usePrefs()
  return (
    <>
      <Title>{tr('个人资料')}</Title>
      <Group>
        <div className="py-4">
          <label className="text-[13.5px] text-ink" htmlFor="pf-name">
            {tr('怎么称呼你')}
          </label>
          <input id="pf-name" value={p.name} maxLength={40} onChange={(e) => setPrefs({ name: e.target.value })} className={clsx(FIELD, 'mt-2')} />
        </div>
        <div className="border-t border-border-soft/70 py-4">
          <label className="flex items-center gap-1.5 text-[13.5px] text-ink" htmlFor="pf-about">
            {tr('偏好')}
            <Tip label={tr('只存在本机')} side="right">
              <Lock size={11} strokeWidth={1.8} className="text-sepia-muted" />
            </Tip>
          </label>
          <textarea
            id="pf-about"
            rows={5}
            value={p.about}
            maxLength={2000}
            onChange={(e) => setPrefs({ about: e.target.value })}
            placeholder={tr('例如：提交信息用中文；先写复现测试')}
            className={clsx(FIELD, 'mt-2 resize-none leading-relaxed')}
          />
        </div>
      </Group>
    </>
  )
}

/* ---------------------------------------------------------------- 模型 */

function ModelSection() {
  const p = usePrefs()
  return (
    <>
      <Title>{tr('模型')}</Title>
      <Group title={tr('默认')}>
        <Row label={tr('模型')}>
          <div className="flex gap-1.5">
            {MODELS.map((m) => (
              <Tip key={m.id} label={m.note} side="bottom">
                <button
                  type="button"
                  disabled={!m.available}
                  onClick={() => setPrefs({ model: m.id })}
                  className={clsx(
                    'chip transition-colors duration-300 disabled:cursor-not-allowed disabled:opacity-45',
                    p.model === m.id && 'border-amber/60 text-ink',
                  )}
                >
                  {p.model === m.id && <Check size={11} strokeWidth={2} className="text-amber-ink" />}
                  {m.name}
                </button>
              </Tip>
            ))}
          </div>
        </Row>
        <Row label={tr('思考强度')}>
          <Segmented
            value={p.thinking}
            onChange={(thinking) => setPrefs({ thinking })}
            options={THINKING_LEVELS.map((t) => ({ id: t.id, label: t.label }))}
            testId="settings-effort"
          />
        </Row>
      </Group>
      <Group title={tr('连接')}>
        <ApiKeyRow />
        <Row label={tr('运行方式')}>
          <CoreModePicker />
        </Row>
      </Group>
    </>
  )
}

function ApiKeyRow() {
  const [state, setState] = useState<SecretState | null>(null)
  const [editing, setEditing] = useState(false)
  const [v, setV] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    secretStatus().then(setState, () => setState('unsupported'))
  }, [])
  const save = async () => {
    setBusy(true)
    try {
      await secretSet(v)
      setState('set')
      setEditing(false)
      toast(tr('已存入系统凭据库'))
    } catch (e) {
      toast(String(e instanceof Error ? e.message : e))
    } finally {
      setV('')
      setBusy(false)
    }
  }
  return (
    <div data-testid="api-key-row" className="border-b border-border-soft/70 py-4">
      <div className="flex items-center justify-between gap-4">
        <span className="flex items-center gap-2 text-[13.5px] text-ink">
          <KeyRound size={14} strokeWidth={1.6} className="text-sepia" />
          {tr('DeepSeek API 密钥')}
        </span>
        <span className="flex items-center gap-2">
          {state === 'set' && (
            <span className="inline-flex items-center gap-1 rounded-full bg-sage/15 px-2 py-0.5 text-[11px] text-sage">
              <Lock size={10} strokeWidth={2} /> {tr('已存入凭据库')}
            </span>
          )}
          {state === 'unset' && <span className="text-[11.5px] text-sepia-muted">{tr('未设置')}</span>}
          {state === 'unsupported' && (
            <Tip label={tr('浏览器预览无法访问系统凭据库')} side="top-end">
              <span className="text-[11.5px] text-sepia-muted">{tr('仅桌面应用')}</span>
            </Tip>
          )}
          {state && state !== 'unsupported' && !editing && (
            <button type="button" onClick={() => setEditing(true)} className="chip hover:text-amber-ink">
              {state === 'set' ? tr('更换') : tr('设置')}
            </button>
          )}
          {state === 'set' && !editing && (
            <button
              type="button"
              onClick={() => secretClear().then(() => (setState('unset'), toast(tr('已清除'))), (e) => toast(String(e)))}
              className="chip hover:text-rose-ink"
            >
              {tr('清除')}
            </button>
          )}
        </span>
      </div>
      <AnimatePresence initial={false}>
        {editing && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 420, damping: 38 }}
            className="overflow-hidden"
          >
            <div className="flex gap-2 pt-3">
              <input
                type="password"
                autoComplete="off"
                spellCheck={false}
                autoFocus
                value={v}
                onChange={(e) => setV(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && v.trim() && void save()}
                placeholder="sk-…"
                className={clsx(FIELD, 'font-mono')}
                aria-label={tr('API 密钥')}
              />
              <button type="button" disabled={!v.trim() || busy} onClick={() => void save()} className="rounded-lg bg-ink px-3.5 text-[13px] text-parchment disabled:opacity-45">
                {tr('保存')}
              </button>
              <button type="button" onClick={() => (setEditing(false), setV(''))} className="rounded-lg px-3 text-[13px] text-ink-soft hover:bg-panel-raised">
                {tr('取消')}
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

/* ---------------------------------------------------------------- 预算 */

function Budget() {
  const p = usePrefs()
  const now = useNow()
  const bj = beijingNow(now)
  const gate = gateStatus(now)
  const spent = useMemo(() => ledger.reduce((s, r) => s + rowCost(r), 0), [])
  const hhmm = `${String(bj.hh).padStart(2, '0')}:${String(bj.mm).padStart(2, '0')}`
  return (
    <>
      <Title>{tr('预算')}</Title>
      <Group title={tr('上限')}>
        <Row label={tr('单任务上限')} hint={tr('最高 ¥{0}', MAX_COST_CAP.toFixed(2))} testId="max-cost-row">
          <input
            type="range"
            min={0.1}
            max={MAX_COST_CAP}
            step={0.05}
            value={p.maxCost}
            onChange={(e) => setPrefs({ maxCost: Math.round(Number(e.target.value) * 100) / 100 })}
            aria-label={tr('单任务上限')}
            className="range-ink w-40"
          />
          <span className="w-14 text-right font-serif text-[16px] tabular-nums text-ink">¥{p.maxCost.toFixed(2)}</span>
        </Row>
        <Row label={tr('总预算')}>
          <span className="font-serif text-[16px] tabular-nums text-ink">¥{BUDGET_TOTAL}</span>
          <span className="text-[11.5px] text-sepia-muted">{tr('已花 ¥{0}', spent.toFixed(2))}</span>
        </Row>
      </Group>

      <Group title={tr('高峰闸门')}>
        <div className="py-5">
          <div className="flex flex-wrap items-center gap-3">
            <span
              className={clsx(
                'inline-flex items-center gap-2 rounded-full px-3.5 py-1 font-serif text-[15px] font-medium',
                gate.inPeak ? 'bg-rose-ink/12 text-rose-ink' : 'bg-sage/14 text-sage',
              )}
            >
              <span className={clsx('pulse-dot h-2 w-2 rounded-full', gate.inPeak ? 'bg-rose-ink' : 'bg-sage')} />
              {gate.inPeak ? tr('高峰') : tr('空闲')}
            </span>
            <Tip label={tr('北京时间')} side="bottom">
              <span className="font-mono text-[13px] tabular-nums text-ink-soft">
                {WEEK[bj.day]} {hhmm}
              </span>
            </Tip>
            <Tip label={tr('下次切换')} side="bottom">
              <span className="chip">
                <ArrowRight size={11} strokeWidth={1.7} />
                {gate.nextShort}
              </span>
            </Tip>
          </div>
          <DayBar minutes={bj.minutes} weekday={gate.weekday} />
          <WeekGrid today={bj.day} />
        </div>
        <Row label={tr('高峰时段也允许真实调用')} hint={tr('2× 价 · 只影响真实模式')}>
          <Toggle on={p.allowPeak} onChange={(allowPeak) => setPrefs({ allowPeak })} danger testId="allow-peak" />
        </Row>
      </Group>

      <div className="paper-card overflow-hidden rounded-2xl">
        <div className="flex items-center gap-2 px-5 py-3">
          <p className="font-serif text-[14px] text-ink-soft">{tr('账本')}</p>
          <Tip label={tr('空闲价 · 命中 {0} / 未命中 {1} / 输出 {2} 元每百万 token', PRICE.idle.hit, PRICE.idle.miss, PRICE.idle.out)} side="right">
            <Info size={12} strokeWidth={1.6} className="text-sepia-muted" />
          </Tip>
        </div>
        <table className="w-full text-left text-[12px]">
          <thead className="border-y border-border-soft bg-parchment/60 text-[10.5px] tracking-wide text-sepia-muted">
            <tr>
              <th className="px-5 py-2 font-normal">{tr('时间')}</th>
              <th className="px-2 py-2 font-normal">{tr('任务')}</th>
              <th className="px-2 py-2 font-normal">{tr('模式')}</th>
              <th className="px-2 py-2 text-right font-normal">{tr('命中率')}</th>
              <th className="px-5 py-2 text-right font-normal">{tr('花费')}</th>
            </tr>
          </thead>
          <tbody className="selectable text-ink-soft">
            {ledger.map((r) => {
              const total = r.hitM + r.missM
              const c = rowCost(r)
              return (
                <tr key={r.id} className="border-b border-border-soft/70 last:border-0">
                  <td className="px-5 py-2.5 font-mono text-[11px] text-sepia">{r.when}</td>
                  <td className="px-2 py-2.5">{r.task}</td>
                  <td className="px-2 py-2.5 text-sepia">{tr(r.mode)}</td>
                  <td className="px-2 py-2.5 text-right tabular-nums">{((r.hitM / total) * 100).toFixed(0)}%</td>
                  <td className={clsx('px-5 py-2.5 text-right tabular-nums', c > p.maxCost && 'text-rose-ink')}>¥{c.toFixed(2)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </>
  )
}

/* ---------------------------------------------------------------- 权限 */

/** spec 006 v3（0.2.1）：四种模式；沙箱后端是单独的设置（见“沙箱”分区），与模式正交 */
const PERMISSION_OPTIONS: { id: SavedMode; label: string; note: string }[] = [
  { id: 'plan', label: tr('只读模式'), note: tr('只看不改，先出方案') },
  { id: 'ask', label: tr('询问模式'), note: tr('改文件、跑命令前都问你；规则照常生效') },
  { id: 'auto_review', label: tr('模型自动审批模式'), note: tr('有风险的操作由审核模型按策略批准或拒绝，没把握再问你') },
]

const RULES = parseRules(defaultRulesYaml)
const RULE_LABEL: Record<RuleKind, string> = { deny: tr('拒绝'), ask: tr('询问'), allow: tr('允许') }

function Permissions() {
  const p = usePrefs()
  const armed = useUnrestrictedArmed()
  const [dlg, setDlg] = useState(false)
  const [kind, setKind] = useState<RuleKind>('deny')
  return (
    <>
      <Title>{tr('权限')}</Title>
      <Group title={tr('模式')}>
        <div role="radiogroup" className="py-2">
          {PERMISSION_OPTIONS.map((o) => {
            const active = p.permissionMode === o.id && !armed
            return (
              <button
                key={o.id}
                type="button"
                role="radio"
                aria-checked={active}
                data-testid={`perm-${o.id}`}
                onClick={() => (disarmUnrestricted(), setPrefs({ permissionMode: o.id }))}
                className="flex w-full items-start gap-3 rounded-lg px-1 py-2.5 text-left transition-colors duration-300 hover:bg-parchment/50"
              >
                <span className="pt-0.5"><Radio on={active} /></span>
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="text-[13.5px] text-ink">{o.label}</span>
                  <span className="text-[11.5px] leading-relaxed text-sepia-muted" data-allow-wrap>{o.note}</span>
                </span>
              </button>
            )
          })}
          <button
            type="button"
            role="radio"
            aria-checked={armed}
            data-testid="perm-full_access"
            onClick={() => (armed ? disarmUnrestricted() : setDlg(true))}
            className="mt-1 flex w-full items-start gap-3 rounded-lg border border-rose-ink/30 bg-rose-ink/[0.05] px-2 py-2.5 text-left transition-colors duration-300 hover:bg-rose-ink/[0.09]"
          >
            <span className="pt-0.5"><Radio on={armed} danger /></span>
            <span className="flex min-w-0 flex-1 flex-col gap-0.5">
              <span className="flex items-center gap-1.5 text-[13.5px] font-medium text-rose-ink">
                <ShieldAlert size={14} strokeWidth={1.7} className="shrink-0" />
                {tr('完全访问模式')}
              </span>
              <span className="text-[11.5px] leading-relaxed text-rose-ink/85" data-allow-wrap>
                {armed ? tr('已就绪 · 只用于下一个任务') : tr('不询问、不拒绝；每个任务两步确认，结束自动恢复')}
              </span>
            </span>
          </button>
          {p.permissionMode === 'auto_review' && !armed && (
            <p data-testid="auto-review-note" data-allow-wrap className="mt-2 rounded-lg bg-parchment/60 px-3 py-2 text-[11.5px] leading-relaxed text-sepia">
              {coreMode() === 'demo'
                ? tr('演示模式用规则审核代替模型（¥0）。')
                : tr('审核模型：DeepSeek Flash（不思考），每次约 ¥0.0003，计入账单并写审计日志。')}
            </p>
          )}
        </div>
      </Group>
      <UnrestrictedDialog open={dlg} onClose={() => setDlg(false)} onArm={armUnrestricted} />

      <Group title={tr('自定义规则')}>
        <RulesEditor />
      </Group>

      <Group title={tr('内置规则')}>
        <div className="flex items-center justify-between gap-3 border-b border-border-soft/70 py-3">
          <Segmented<RuleKind>
            value={kind}
            onChange={setKind}
            options={(['deny', 'ask', 'allow'] as RuleKind[]).map((k) => ({ id: k, label: `${RULE_LABEL[k]} ${RULES[k].length}` }))}
            testId="rule-kind"
          />
          <span className="min-w-0 truncate text-[11.5px] text-sepia-muted">{tr('只读 · 自定义规则优先')}</span>
        </div>
        <ul data-testid="rule-list" className="selectable max-h-[300px] overflow-y-auto scroll-soft py-2">
          {RULES[kind].map((r) => (
            <li key={r.rule + (r.backends ?? []).join()} className="flex items-center gap-2 py-1 font-mono text-[11.5px] text-ink-soft">
              {r.exception && <span className="rounded bg-sage/15 px-1 text-[10px] text-sage">{tr('例外')}</span>}
              <span className="truncate">{r.rule}</span>
              {r.backends && <span className="ml-auto shrink-0 text-[10.5px] text-sepia-muted">{tr('仅 {0}', r.backends.join(' / '))}</span>}
            </li>
          ))}
          {RULES[kind].length === 0 && <li className="py-3 text-center text-[12px] text-sepia-muted">{tr('无')}</li>}
        </ul>
      </Group>
    </>
  )
}

function Radio({ on, danger }: { on: boolean; danger?: boolean }) {
  return (
    <span className={clsx('flex h-4 w-4 shrink-0 items-center justify-center rounded-full border transition-colors duration-300', on ? (danger ? 'border-rose-ink' : 'border-amber') : 'border-border')}>
      <AnimatePresence>
        {on && (
          <motion.span
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            exit={{ scale: 0 }}
            transition={{ type: 'spring', stiffness: 700, damping: 30 }}
            className={clsx('h-2 w-2 rounded-full', danger ? 'bg-rose-ink' : 'bg-amber')}
          />
        )}
      </AnimatePresence>
    </span>
  )
}

/* ---------------------------------------------------------------- 沙箱 */

const BACKEND_OPTIONS: { id: Backend; label: string; note: string }[] = [
  { id: 'auto', label: tr('自动'), note: tr('有 Docker 用 Docker，否则本机工作树') },
  { id: 'docker', label: 'Docker', note: tr('断网容器，最安全') },
  { id: 'none', label: tr('本机'), note: tr('独立 git 工作树，无隔离') },
]

function Sandbox() {
  const p = usePrefs()
  return (
    <>
      <Title>{tr('沙箱')}</Title>
      <p className="-mt-2 mb-4 text-[12px] leading-relaxed text-sepia-muted" data-allow-wrap>{tr('沙箱后端与权限模式相互独立：模式决定“问不问”，沙箱决定“在哪儿跑”。')}</p>
      <Group title={tr('后端')}>
        <div role="radiogroup" className="py-2">
          {BACKEND_OPTIONS.map((o) => (
            <button
              key={o.id}
              type="button"
              role="radio"
              aria-checked={p.backend === o.id}
              data-testid={`backend-${o.id}`}
              onClick={() => setPrefs({ backend: o.id })}
              className="flex w-full items-center gap-3 rounded-lg px-1 py-2.5 text-left transition-colors duration-300 hover:bg-parchment/50"
            >
              <Radio on={p.backend === o.id} />
              <span className="shrink-0 whitespace-nowrap text-[13.5px] text-ink">{o.label}</span>
              <span className="min-w-0 truncate text-[11.5px] text-sepia-muted" title={o.note}>{o.note}</span>
            </button>
          ))}
        </div>
      </Group>
      <Group title={tr('环境与一键安装')}>
        <SandboxInstall />
      </Group>
    </>
  )
}

/* ---------------------------------------------------------------- 连接器 · 隐私 · 关于 */

function Connectors() {
  return (
    <>
      <Title>{tr('连接器')}</Title>
      <Group>
        {['GitHub', 'GitLab', 'Gitee'].map((n) => (
          <Row key={n} label={n}>
            <button type="button" onClick={() => notYet(tr('连接 {0}', n))} className="chip hover:text-amber-ink">
              {tr('连接')}
            </button>
          </Row>
        ))}
      </Group>
    </>
  )
}

function Privacy() {
  const [confirm, setConfirm] = useState(false)
  return (
    <>
      <Title>{tr('隐私')}</Title>
      <Group>
        <Row label={tr('数据位置')} hint={tr('会话、轨迹与证据都在本机 ~/.triwitness')}>
          <Lock size={14} strokeWidth={1.6} className="text-sage" />
        </Row>
        <Row label={tr('导出数据')} hint={tr('会话、项目和设置（JSON）；不含 API 密钥')}>
          <button type="button" data-testid="export-data" onClick={() => void saveText(exportFileStamp(), collectLocalData(), 'application/json')} className="chip hover:text-amber-ink">
            {tr('导出')}
          </button>
        </Row>
        <Row label={tr('清除本机会话记录')}>
          <button type="button" data-testid="clear-history" onClick={() => setConfirm(true)} className="chip hover:text-rose-ink">
            {tr('清除')}
          </button>
        </Row>
      </Group>
      <ClearHistoryDialog
        open={confirm}
        onClose={() => setConfirm(false)}
        onConfirm={() => {
          clearHistory()
          window.location.reload()
        }}
      />
    </>
  )
}

function About({ onShortcuts }: { onShortcuts: () => void }) {
  const [licenses, setLicenses] = useState(false)
  return (
    <>
      <Title>{tr('关于')}</Title>
      <Group>
        <Row label={tr('三证 TriWitness')}>
          <span className="font-mono text-[12px] text-sepia">v{VERSION}</span>
        </Row>
        <Row label={tr('快捷键')}>
          <button type="button" onClick={onShortcuts} className="chip hover:text-amber-ink">
            <Keyboard size={11} strokeWidth={1.7} /> Ctrl /
          </button>
        </Row>
        <Row label={tr('检查更新')}>
          <button type="button" onClick={() => notYet(tr('检查更新'))} className="chip hover:text-amber-ink">
            {tr('检查')}
          </button>
        </Row>
        <Row label={tr('开源许可')}>
          <button type="button" data-testid="open-licenses" onClick={() => setLicenses(true)} className="chip hover:text-amber-ink">
            {tr('查看')}
          </button>
        </Row>
      </Group>
      <LicensesDialog open={licenses} onClose={() => setLicenses(false)} />
    </>
  )
}

const MODES: { id: CoreMode; label: string; tip: string }[] = [
  { id: 'demo', label: tr('演示'), tip: tr('脚本模型 · 示例仓库 · ¥0') },
  { id: 'replay', label: tr('回放'), tip: tr('用录好的模型回复 · ¥0') },
  { id: 'live', label: tr('真实'), tip: tr('deepseek-flash · 计费 · 受高峰闸门约束') },
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
              mode === m.id ? 'bg-ink text-parchment' : 'text-ink-soft hover:text-amber-ink',
            )}
          >
            {m.label}
          </button>
        </Tip>
      ))}
    </div>
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
          {tr('高峰')}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-3 rounded-sm bg-sage/25" />
          {tr('空闲')}
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
