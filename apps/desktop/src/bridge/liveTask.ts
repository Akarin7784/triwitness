/**
 * 一次真实任务（UI-10）：收核心的行，攒事件与控制消息；对外既是 EventSource（推流 / 折叠复用原有路径），
 * 也暴露审批、结果、进程状态。
 */
import type { AnyEvent } from '../data/events'
import type { EventSource, SubscribeOptions } from '../data/sources/types'
import { parseBridgeLine, type ResultMsg } from './protocol'
import { t } from '../lib/i18n'

export interface PendingApproval {
  requestId: string
  seq: number
  tool: string
  action: string
  reason: string
  risk: string | null
  suggestedRule: string | null
}

export interface LiveSnapshot {
  runId: string | null
  runDir: string | null
  mode: string | null
  approvals: PendingApproval[]
  /** 已结案的审批：request_id → 显示文字 */
  resolved: Record<string, string>
  result: ResultMsg | null
  error: string | null
  exited: boolean
  exitCode: number | null
  /** 当前权限模式（核心 mode_changed 事件）；risk=high 时界面常驻红色横幅 */
  permission: { mode: string; risk: 'normal' | 'high' } | null
}

export interface TaskMeta {
  id: string
  title: string
  repo: string
  mode: string
  runId?: string | null
  runDir?: string | null
  /** 核心进程 key（Tauri core_* / 开发桥），续上实时流用 */
  key?: string
  startedAt: number
  /** 原始任务文本与选择（重试 / 编辑后重发用；勇士模式确认短语从不保存） */
  issue?: string
  model?: string
  thinking?: string
  /** 随任务交给核心的附件名（界面显示用） */
  attachments?: string[]
  /** 附件落盘路径（重试 / 编辑后重发时原样带上） */
  attachmentPaths?: string[]
  /** 结束时写入：终态与结论，侧栏用 */
  status?: string | null
  verdict?: string | null
  /** 结论卡数据（续上时 stdout 已不在，靠它重现） */
  result?: ResultMsg | null
}

export class LiveTask implements EventSource {
  readonly id: string
  private events: AnyEvent[] = []
  private seqs = new Set<number>()
  private listeners = new Set<(e: AnyEvent) => void>()
  private watchers = new Set<() => void>()
  private _afterSeq = -1
  snapshot: LiveSnapshot = {
    runId: null,
    runDir: null,
    mode: null,
    approvals: [],
    resolved: {},
    result: null,
    error: null,
    exited: false,
    exitCode: null,
    permission: null,
  }

  constructor(id: string) {
    this.id = id
  }

  get afterSeq() {
    return this._afterSeq
  }

  get allEvents(): readonly AnyEvent[] {
    return this.events
  }

  private update(patch: Partial<LiveSnapshot>) {
    this.snapshot = { ...this.snapshot, ...patch }
    for (const w of this.watchers) w()
  }

  /** 状态变化（审批 / 结果 / 退出）时回调；返回退订 */
  watch(fn: () => void): () => void {
    this.watchers.add(fn)
    return () => this.watchers.delete(fn)
  }

  /** 喂一行核心输出（实时或续传读盘都走这里）；幂等 */
  push(line: string) {
    const parsed = parseBridgeLine(line)
    if (!parsed) return
    if (parsed.type === 'control') {
      const m = parsed.msg
      if (m.bridge === 'hello') this.update({ mode: m.mode })
      else if (m.bridge === 'run') this.update({ runId: m.run_id, runDir: m.run_dir })
      else if (m.bridge === 'result') this.update({ result: m, approvals: [] })
      else if (m.bridge === 'error') this.update({ error: m.message, approvals: [] })
      return
    }
    const e = parsed.event
    if (this.seqs.has(e.seq)) return
    this.seqs.add(e.seq)
    this.events.push(e)
    if (this.events.length > 1 && this.events[this.events.length - 2].seq > e.seq) {
      this.events.sort((a, b) => a.seq - b.seq)
    }
    this._afterSeq = Math.max(this._afterSeq, e.seq)
    if (!this.snapshot.runId) this.update({ runId: e.run_id })
    this.track(e)
    for (const l of this.listeners) l(e)
  }

  private track(e: AnyEvent) {
    if (e.kind === 'approval_requested') {
      const p = e.payload as Record<string, unknown>
      const req: PendingApproval = {
        requestId: String(p.request_id),
        seq: e.seq,
        tool: String(p.tool ?? ''),
        action: String(p.action ?? ''),
        reason: String(p.reason ?? ''),
        risk: (p.risk as string | null) ?? null,
        suggestedRule: (p.suggested_rule as string | null) ?? null,
      }
      if (!(req.requestId in this.snapshot.resolved)) {
        this.update({ approvals: [...this.snapshot.approvals.filter((a) => a.requestId !== req.requestId), req] })
      }
    } else if (e.kind === 'approval_resolved') {
      const p = e.payload as Record<string, unknown>
      const rid = String(p.request_id)
      const text = String(p.display ?? (p.decision === 'allow' ? t('已允许') : t('已拒绝')))
      this.update({
        approvals: this.snapshot.approvals.filter((a) => a.requestId !== rid),
        resolved: { ...this.snapshot.resolved, [rid]: text },
      })
    } else if (e.kind === 'mode_changed') {
      const p = e.payload as Record<string, unknown>
      this.update({ permission: { mode: String(p.to_mode ?? ''), risk: p.risk === 'high' ? 'high' : 'normal' } })
    } else if (e.kind === 'task_finished') {
      this.update({ approvals: [] })
    }
  }

  exit(code: number | null) {
    this.update({ exited: true, exitCode: code, approvals: [] })
  }

  fail(message: string) {
    this.update({ error: message, exited: true, approvals: [] })
  }

  subscribe(onEvent: (e: AnyEvent) => void, opts: SubscribeOptions = {}) {
    const after = opts.afterSeq ?? -1
    for (const e of this.events) if (e.seq > after) onEvent(e)
    this.listeners.add(onEvent)
    return () => {
      this.listeners.delete(onEvent)
    }
  }

  /** LiveTask 生命周期由任务表管理；切换会话时只退订，不关闭 */
  close() {}
}

/** 结果卡用：pr.md 摘要（去掉标题行与空行，取前 n 行） */
export function prSummary(md: string | null, n = 8): string[] {
  if (!md) return []
  return md
    .split(/\r?\n/)
    .map((l) => l.trimEnd())
    .filter((l) => l.trim() && !/^<!--/.test(l.trim()))
    .slice(0, n)
}
