/**
 * 真实任务表（UI-10）：进程内注册表 + localStorage 里的任务清单（标题 / 仓库 / run_dir / 进程 key）。
 * 界面刷新或重开后据此“续上”：进程还在就重新接实时流，否则从 run_dir/trajectory.jsonl 读回全程。
 */
import { useCallback, useEffect, useState, useSyncExternalStore } from 'react'
import { LiveTask, type TaskMeta } from './liveTask'
import { approveCmd, CANCEL_CMD, type ApprovalScope, type CoreMode } from './protocol'
import { getTransport, type CoreTransport } from './transport'

const TASKS_KEY = 'tw.live.tasks'
const MODE_KEY = 'tw.core.mode'
const REPO_KEY = 'tw.core.repo'
const MAX_TASKS = 30

const registry = new Map<string, LiveTask>()
const detach = new Map<string, () => void>()

export function liveTaskFor(id: string): LiveTask | null {
  return registry.get(id) ?? null
}

function storage(): Storage | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage
  } catch {
    return null
  }
}

export function loadMetas(): TaskMeta[] {
  try {
    const v = JSON.parse(storage()?.getItem(TASKS_KEY) ?? '[]')
    return Array.isArray(v) ? (v as TaskMeta[]) : []
  } catch {
    return []
  }
}

function saveMetas(metas: TaskMeta[]) {
  storage()?.setItem(TASKS_KEY, JSON.stringify(metas.slice(0, MAX_TASKS)))
}

export function coreMode(): CoreMode {
  const v = storage()?.getItem(MODE_KEY)
  return v === 'replay' || v === 'live' ? v : 'demo'
}

export function setCoreMode(m: CoreMode) {
  storage()?.setItem(MODE_KEY, m)
}

export function lastRepo(): string {
  return storage()?.getItem(REPO_KEY) ?? ''
}

/** 演示模式下仓库可留空：核心在 ~/.triwitness/demo/verses 建一个示例仓库 */
export function defaultDemoRepo(): string {
  return '~/.triwitness/demo/verses'
}

/** 把 metas 变成可订阅的外部 store，供侧栏 / 结果卡同步 */
let metas: TaskMeta[] = loadMetas()
const metaSubs = new Set<() => void>()
function setMetas(next: TaskMeta[]) {
  metas = next
  saveMetas(next)
  for (const s of metaSubs) s()
}
function patchMeta(id: string, patch: Partial<TaskMeta>) {
  setMetas(metas.map((m) => (m.id === id ? { ...m, ...patch } : m)))
}

export function useTaskMetas(): TaskMeta[] {
  return useSyncExternalStore(
    (fn) => {
      metaSubs.add(fn)
      return () => metaSubs.delete(fn)
    },
    () => metas,
  )
}

/** 一个任务的快照（审批 / 结果 / 退出），随 LiveTask.watch 刷新 */
export function useLiveSnapshot(task: LiveTask | null) {
  return useSyncExternalStore(
    (fn) => (task ? task.watch(fn) : () => {}),
    () => task?.snapshot ?? null,
  )
}

function wire(t: LiveTask, transport: CoreTransport, key: string, id: string) {
  t.watch(() => {
    const s = t.snapshot
    const m = metas.find((x) => x.id === id)
    if (!m) return
    const patch: Partial<TaskMeta> = {}
    if (s.runId && m.runId !== s.runId) patch.runId = s.runId
    if (s.runDir && m.runDir !== s.runDir) patch.runDir = s.runDir
    if (s.result && m.status !== s.result.status) {
      patch.status = s.result.status
      patch.verdict = s.result.verdict
      patch.result = s.result
    }
    if (s.exited && !m.status && !s.result) patch.status = s.error ? 'error' : 'cancelled'
    if (Object.keys(patch).length) patchMeta(id, patch)
  })
  return transport
    .attach(key, (line) => t.push(line), (code) => t.exit(code))
    .then((un) => detach.set(id, un))
}

export async function startTask(opts: { repo: string; issue: string; mode: CoreMode }): Promise<string> {
  const transport = await getTransport()
  if (!transport) throw new Error('未连接核心')
  const repo = opts.repo.trim() || (opts.mode === 'demo' ? defaultDemoRepo() : '')
  if (!repo) throw new Error('先选仓库')
  const key = await transport.start({ repo, issue: opts.issue, mode: opts.mode })
  const id = `${Date.now().toString(36)}-${key}`
  const t = new LiveTask(id)
  registry.set(id, t)
  const title = opts.issue.trim().split(/\r?\n/)[0].slice(0, 60) || (opts.mode === 'demo' ? '演示任务' : '新任务')
  setMetas([{ id, title, repo, mode: opts.mode, key, startedAt: Date.now() }, ...metas])
  if (opts.repo.trim()) storage()?.setItem(REPO_KEY, opts.repo.trim())
  await wire(t, transport, key, id)
  return id
}

/** 续上：进程在 → 读盘补齐 + 接实时流；不在 → 读盘回放全程（只读） */
export async function resumeTask(id: string): Promise<LiveTask | null> {
  const existing = registry.get(id)
  if (existing) return existing
  const m = metas.find((x) => x.id === id)
  if (!m) return null
  const t = new LiveTask(id)
  registry.set(id, t)
  const transport = await getTransport()
  if (!transport) {
    t.fail('未连接核心')
    return t
  }
  const key = (m).key
  const alive = key ? await transport.alive(key).catch(() => false) : false
  if (m.runDir) {
    try {
      for (const line of await transport.readRun(m.runDir, -1)) t.push(line)
    } catch (e) {
      if (!alive) t.fail(String(e))
    }
  }
  if (alive && key) await wire(t, transport, key, id)
  else {
    if (m.result) t.push(JSON.stringify(m.result))
    if (!t.snapshot.error) t.exit(null)
  }
  return t
}

export async function approve(id: string, requestId: string, decision: 'allow' | 'deny', scope: ApprovalScope) {
  const transport = await getTransport()
  const key = metas.find((x) => x.id === id)?.key
  if (!transport || !key) throw new Error('任务已断开')
  await transport.send(key, approveCmd(requestId, decision, scope))
}

export async function cancelTask(id: string) {
  const transport = await getTransport()
  const key = metas.find((x) => x.id === id)?.key
  if (!transport || !key) return
  await transport.cancel(key).catch(() => transport.send(key, CANCEL_CMD).catch(() => {}))
}

/** 核心是否可用（Tauri 或开发桥） */
export function useCoreAvailable(): boolean | null {
  const [ok, setOk] = useState<boolean | null>(null)
  useEffect(() => {
    let live = true
    getTransport().then((t) => live && setOk(!!t))
    return () => {
      live = false
    }
  }, [])
  return ok
}

/** 选中某个真实任务时确保它已注册（续上），返回任务 */
export function useLiveTask(id: string | null): LiveTask | null {
  const [, bump] = useState(0)
  const refresh = useCallback(() => bump((n) => n + 1), [])
  useEffect(() => {
    if (!id || registry.has(id)) return
    let live = true
    resumeTask(id).then(() => live && refresh())
    return () => {
      live = false
    }
  }, [id, refresh])
  return id ? (registry.get(id) ?? null) : null
}
