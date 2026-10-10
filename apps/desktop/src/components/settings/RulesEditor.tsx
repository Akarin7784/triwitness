import { useEffect, useEffectEvent, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Check, Loader2, Pencil, Plus, Trash2, X } from 'lucide-react'
import clsx from 'clsx'
import { coreTool } from '../../lib/coreTool'
import { coreMode, defaultDemoRepo, lastRepo } from '../../bridge/liveStore'
import { toast } from '../../lib/toast'
import { FIELD } from '../../lib/ui'
import { t as tr } from '../../lib/i18n'

type Kind = 'allow' | 'ask' | 'deny'
type LayerId = 'user' | 'local'
interface Layer {
  path: string
  allow: string[]
  ask: string[]
  deny: string[]
}
const KINDS: { id: Kind; label: string; cls: string }[] = [
  { id: 'allow', label: tr('允许'), cls: 'bg-sage/15 text-sage' },
  { id: 'ask', label: tr('询问'), cls: 'bg-amber/15 text-amber-ink' },
  { id: 'deny', label: tr('拒绝'), cls: 'bg-rose-ink/12 text-rose-ink' },
]
const SPRING = { type: 'spring', stiffness: 460, damping: 36 } as const

function repoArg(): string {
  return lastRepo() || (coreMode() === 'demo' ? defaultDemoRepo() : '')
}

/** 用同一个解析器（核心 parse_rule）校验；空串不校验 */
function useValidation(kind: Kind, rule: string) {
  const [state, setState] = useState<{ rule: string; kind: Kind; error: string | null } | null>(null)
  useEffect(() => {
    if (!rule.trim()) return
    let live = true
    const t = window.setTimeout(() => {
      void coreTool(['permissions', 'validate', '--kind', kind, '--rule', rule]).then((r) => {
        if (live) setState({ rule, kind, error: r.ok ? null : r.error })
      })
    }, 280)
    return () => {
      live = false
      window.clearTimeout(t)
    }
  }, [kind, rule])
  if (!rule.trim()) return { checking: false, error: null as string | null, ok: false }
  const fresh = state && state.rule === rule && state.kind === kind
  return { checking: !fresh, error: fresh ? state.error : null, ok: !!fresh && !state.error }
}

/** 自定义权限规则（照 Claude Code 的 allow / ask / deny）：用户层 + 此仓库层；写入前由核心校验 */
export function RulesEditor() {
  const [layers, setLayers] = useState<Partial<Record<LayerId, Layer>> | null>(null)
  const [offline, setOffline] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const repo = repoArg()

  const load = () =>
    coreTool<{ layers: Record<LayerId, Layer> }>(['permissions', 'list', ...(repo ? ['--repo', repo] : [])]).then((r) => {
      if (r.ok) {
        setLayers(r.data.layers)
        setErr(null)
      } else if (!r.ok && r.offline) setOffline(true)
      else setErr(r.error)
    })
  const initial = useEffectEvent(() => void load())
  useEffect(() => initial(), [])

  if (offline) return <p className="py-4 text-[12.5px] text-sepia-muted">{tr('连接核心后可以编辑规则（浏览器预览里只读）。')}</p>
  if (!layers) return <p className="flex items-center gap-2 py-4 text-[12.5px] text-sepia-muted">{err ?? <><Loader2 size={12} className="animate-spin" /> {tr('读取中…')}</>}</p>

  const run = async (args: string[], ok: string) => {
    const r = await coreTool(args)
    if (r.ok) {
      toast(ok)
      await load()
      return null
    }
    return r.ok ? null : r.error
  }

  return (
    <div data-testid="rules-editor" className="space-y-5 py-3">
      <AddRule onAdd={(kind, rule) => run(['permissions', 'add', '--kind', kind, '--rule', rule], tr('已添加规则'))} />
      {(['user', 'local'] as LayerId[]).map((id) => {
        const l = layers[id]
        if (!l) return null
        const rows = KINDS.flatMap((k) => l[k.id].map((rule) => ({ kind: k.id, rule })))
        return (
          <div key={id} data-testid={`rules-${id}`}>
            <div className="flex items-baseline justify-between gap-3">
              <p className="text-[12.5px] text-ink">{id === 'user' ? tr('我的规则（本机所有仓库）') : tr('此仓库（审批卡“总是”写入）')}</p>
              <p className="truncate font-mono text-[10.5px] text-sepia-muted" title={l.path}>
                {l.path}
              </p>
            </div>
            <ul className="mt-1.5 rounded-xl border border-border-soft/80">
              <AnimatePresence initial={false}>
                {rows.map((r) => (
                  <motion.li
                    key={`${r.kind}:${r.rule}`}
                    layout
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, pointerEvents: 'none', height: 0 }}
                    transition={SPRING}
                    className="overflow-hidden border-b border-border-soft/60 last:border-b-0"
                  >
                    <RuleRow
                      kind={r.kind}
                      rule={r.rule}
                      onSave={(next) =>
                        run(['permissions', 'add', '--kind', r.kind, '--rule', next, '--replace', r.rule, '--layer', id, ...(id === 'local' ? ['--repo', repo] : [])], tr('已保存'))
                      }
                      onDelete={() => run(['permissions', 'remove', '--kind', r.kind, '--rule', r.rule, '--layer', id, ...(id === 'local' ? ['--repo', repo] : [])], tr('已删除'))}
                    />
                  </motion.li>
                ))}
              </AnimatePresence>
              {rows.length === 0 && <li className="px-3 py-3 text-[12px] text-sepia-muted">{id === 'user' ? tr('还没有自己的规则') : tr('还没有“总是允许”的记录')}</li>}
            </ul>
          </div>
        )
      })}
    </div>
  )
}

function AddRule({ onAdd }: { onAdd: (k: Kind, r: string) => Promise<string | null> }) {
  const [kind, setKind] = useState<Kind>('allow')
  const [rule, setRule] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const v = useValidation(kind, rule)
  const add = async () => {
    if (!v.ok || busy) return
    setBusy(true)
    const e = await onAdd(kind, rule)
    setBusy(false)
    setErr(e)
    if (!e) setRule('')
  }
  return (
    <div>
      <div className="flex items-center gap-2">
        <div role="radiogroup" aria-label={tr('规则类型')} className="flex shrink-0 rounded-lg border border-border-soft p-0.5">
          {KINDS.map((k) => (
            <button
              key={k.id}
              type="button"
              role="radio"
              aria-checked={kind === k.id}
              data-testid={`new-rule-${k.id}`}
              onClick={() => setKind(k.id)}
              className={clsx('rounded-md px-2.5 py-1 text-[12px] transition-colors duration-200', kind === k.id ? k.cls : 'text-sepia hover:text-ink')}
            >
              {k.label}
            </button>
          ))}
        </div>
        <input
          data-testid="new-rule"
          value={rule}
          onChange={(e) => (setRule(e.target.value), setErr(null))}
          onKeyDown={(e) => e.key === 'Enter' && !e.nativeEvent.isComposing && void add()}
          placeholder="Bash(npm run test:*)  ·  Read(./docs/**)  ·  WebFetch(domain:example.com)"
          spellCheck={false}
          aria-invalid={!!v.error}
          className={clsx(FIELD, 'font-mono text-[12px]', v.error && 'border-rose-ink/50')}
        />
        <button
          type="button"
          data-testid="add-rule"
          disabled={!v.ok || busy}
          onClick={() => void add()}
          className="inline-flex h-[38px] shrink-0 items-center gap-1 rounded-xl bg-ink px-3 text-[12.5px] text-parchment transition-colors duration-300 hover:bg-espresso disabled:opacity-40"
        >
          {busy ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />} {tr('添加')}
        </button>
      </div>
      <p data-testid="rule-validation" className={clsx('mt-1.5 min-h-[18px] text-[11.5px]', v.error || err ? 'text-rose-ink' : 'text-sepia-muted')}>
        {err ?? v.error ?? (v.ok ? tr('✓ 规则有效') : v.checking ? tr('校验中…') : tr('格式：工具 或 工具(参数)，* 匹配任意'))}
      </p>
    </div>
  )
}

function RuleRow({ kind, rule, onSave, onDelete }: { kind: Kind; rule: string; onSave: (r: string) => Promise<string | null>; onDelete: () => Promise<string | null> }) {
  const [edit, setEdit] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const v = useValidation(kind, edit ?? '')
  const k = KINDS.find((x) => x.id === kind)!
  const save = async () => {
    if (edit === null) return
    if (edit === rule) return setEdit(null)
    if (!v.ok) return
    const e = await onSave(edit)
    setErr(e)
    if (!e) setEdit(null)
  }
  return (
    <div data-testid="rule-row" className="group flex items-center gap-2 px-3 py-2">
      <span className={clsx('shrink-0 rounded px-1.5 py-px text-[10.5px]', k.cls)}>{k.label}</span>
      {edit === null ? (
        <span className="selectable min-w-0 flex-1 truncate font-mono text-[12px] text-ink-soft">{rule}</span>
      ) : (
        <span className="min-w-0 flex-1">
          <input
            autoFocus
            data-testid="rule-edit-input"
            value={edit}
            spellCheck={false}
            onChange={(e) => (setEdit(e.target.value), setErr(null))}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.nativeEvent.isComposing) void save()
              if (e.key === 'Escape') {
                e.stopPropagation()
                setEdit(null)
              }
            }}
            className={clsx(FIELD, 'py-1 font-mono text-[12px]', (v.error || err) && 'border-rose-ink/50')}
          />
          {(v.error || err) && <span className="mt-1 block text-[11px] text-rose-ink">{err ?? v.error}</span>}
        </span>
      )}
      <span className={clsx('flex shrink-0 items-center gap-0.5 transition-opacity duration-200', edit === null && 'opacity-0 group-hover:opacity-100 focus-within:opacity-100')}>
        {edit === null ? (
          <>
            <button type="button" aria-label={tr('编辑 {0}', rule)} data-testid="rule-edit" onClick={() => setEdit(rule)} className="rounded-md p-1 text-sepia hover:bg-panel-raised hover:text-ink">
              <Pencil size={12} />
            </button>
            <button type="button" aria-label={tr('删除 {0}', rule)} data-testid="rule-delete" onClick={() => void onDelete()} className="rounded-md p-1 text-sepia hover:bg-panel-raised hover:text-rose-ink">
              <Trash2 size={12} />
            </button>
          </>
        ) : (
          <>
            <button type="button" aria-label={tr('保存')} data-testid="rule-save" disabled={edit !== rule && !v.ok} onClick={() => void save()} className="rounded-md p-1 text-sage hover:bg-panel-raised disabled:opacity-40">
              <Check size={13} />
            </button>
            <button type="button" aria-label={tr('取消')} onClick={() => setEdit(null)} className="rounded-md p-1 text-sepia hover:bg-panel-raised">
              <X size={13} />
            </button>
          </>
        )}
      </span>
    </div>
  )
}
