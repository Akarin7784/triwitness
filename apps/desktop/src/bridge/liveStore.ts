/**
 * 真实任务表（UI-10）：进程内注册表 + localStorage 里的任务清单（标题 / 仓库 / run_dir / 进程 key）。
 * 界面刷新或重开后据此“续上”：进程还在就重新接实时流，否则从 run_dir/trajectory.jsonl 读回全程。
 */
import { useCallback, useEffect, useState, useSyncExternalStore } from 'react'
import { LiveTask, type TaskMeta } from './liveTask'
import { approveCmd, CANCEL_CMD, type ApprovalScope, type CoreMode } from './protocol'
import { getTransport, type CoreTransport } from './transport'
import type { RunChoices } from './choices'
import { t as tr } from '../lib/i18n'

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

/** 0.3.1 起正式版只有真实模式；开发构建可用 localStorage `tw.core.mode` = demo / replay 切到脚本 / 回放（测试用） */
export function coreMode(): CoreMode {
  if (!import.meta.env.DEV) return 'live'
  const v = storage()?.getItem(MODE_KEY)
  return v === 'replay' || v === 'demo' ? v : 'live'
}

export function lastRepo(): string {
  return storage()?.getItem(REPO_KEY) ?? ''
}

const RECENT_KEY = 'tw.core.recentRepos'
const MAX_RECENT = 8
const repoKey = (p: string) => p.replace(/\\/g, '/').replace(/\/+$/, '').toLowerCase()

/** 最近用过的仓库（新 → 旧，最多 8 个；Windows 路径大小写 / 斜杠不敏感去重） */
export function recentRepos(): string[] {
  try {
    const v = JSON.parse(storage()?.getItem(RECENT_KEY) ?? '[]')
    const list = Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string' && !!x.trim()) : []
    const last = lastRepo()
    return last && !list.some((x) => repoKey(x) === repoKey(last)) ? [last, ...list].slice(0, MAX_RECENT) : list.slice(0, MAX_RECENT)
  } catch {
    return []
  }
}

export function rememberRepo(path: string) {
  const p = path.trim()
  if (!p) return
  const next = [p, ...recentRepos().filter((x) => repoKey(x) !== repoKey(p))].slice(0, MAX_RECENT)
  storage()?.setItem(RECENT_KEY, JSON.stringify(next))
  storage()?.setItem(REPO_KEY, p)
}

export function forgetRecentRepo(path: string) {
  const next = recentRepos().filter((x) => repoKey(x) !== repoKey(path))
  storage()?.setItem(RECENT_KEY, JSON.stringify(next))
  if (repoKey(lastRepo()) === repoKey(path)) storage()?.removeItem(REPO_KEY)
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

export async function startTask(
  opts: {
    repo: string
    issue: string
    mode: CoreMode
    attachmentNames?: string[]
    userAttachments?: string[]
    /** 多轮对话：上一轮的 run_id */
    parentRun?: string | null
    /** 断点续跑：从这个已停止 / 中断的 run_id 继续（0.3.2） */
    resume?: string | null
  } & RunChoices,
): Promise<string> {
  const transport = await getTransport()
  if (!transport) throw new Error(tr('未连接核心'))
  // 仓库可空：核心先按对话处理，要动手时会请用户选仓库
  const repo = opts.repo.trim()
  const { attachmentNames, userAttachments, parentRun, resume, ...run } = opts
  const key = await transport.start({ ...run, repo, parentRun: parentRun ?? undefined, resume: resume ?? undefined })
  const id = `${Date.now().toString(36)}-${key}`
  const t = new LiveTask(id)
  registry.set(id, t)
  const title = opts.issue.trim().split(/\r?\n/)[0].slice(0, 60) || tr('新会话')
  setMetas([
    { id, title, repo, mode: opts.mode, key, startedAt: Date.now(), issue: opts.issue, model: opts.model, thinking: opts.thinking,
      parentRun: parentRun ?? undefined,
      attachments: attachmentNames?.length ? attachmentNames : undefined,
      attachmentPaths: userAttachments?.length ? userAttachments : undefined },
    ...metas,
  ])
  if (opts.repo.trim()) rememberRepo(opts.repo)
  await wire(t, transport, key, id)
  return id
}

/** 删除任务记录（侧栏删除）；进程还在先停掉 */
export async function forgetTask(id: string) {
  const m = metas.find((x) => x.id === id)
  if (!m) return
  const t = registry.get(id)
  if (t && !t.snapshot.exited && !t.snapshot.result) await cancelTask(id)
  detach.get(id)?.()
  detach.delete(id)
  registry.delete(id)
  setMetas(metas.filter((x) => x.id !== id))
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
    t.fail(tr('未连接核心'))
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
  if (!transport || !key) throw new Error(tr('任务已断开'))
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

/** 多轮对话里之前的各轮（0.3.1）：逐个续上（读盘回放），全部就绪后刷新一次；返回与 ids 对齐的任务 */
export function usePastTasks(ids: string[]): (LiveTask | null)[] {
  const [, bump] = useState(0)
  const sig = ids.join('|')
  useEffect(() => {
    const todo = sig ? sig.split('|').filter((id) => !registry.has(id)) : []
    if (!todo.length) return
    let live = true
    void Promise.all(todo.map((id) => resumeTask(id))).then(() => live && bump((n) => n + 1))
    return () => {
      live = false
    }
  }, [sig])
  return ids.map((id) => registry.get(id) ?? null)
}
