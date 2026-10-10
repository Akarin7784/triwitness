/**
 * tw-events/1 → UI 映射（docs/design/event-protocol.md §3）。纯函数，便于测试。
 */
import type { ChatMessage, RoleId, StreamLine, StreamTone } from '../types'
import { isKnown, type AnyEvent, type TaskState, type TwEvent } from './events'

export const TASK_CAP_DEFAULT = 0.8

const STATE_LABEL: Record<TaskState, string> = {
  received: '接收',
  preparing: '准备沙箱',
  planning: '规划',
  await_plan_approval: '待批计划',
  reproducing: '复现',
  executing: '修复',
  verifying: '复验',
  reviewing: '评审',
  packaging: '整理证据',
  await_pr_approval: '待批 PR',
  pr_opened: 'PR 已开',
  ci_watch: '盯 CI',
  done: '完成',
  needs_human: '待人工',
  budget_exceeded: '预算耗尽',
  failed: '失败',
  cancelled: '已取消',
}

/** 状态 → 由哪个角色主导（用于点亮角色点） */
const STATE_ROLE: Partial<Record<TaskState, RoleId>> = {
  planning: 'planner',
  await_plan_approval: 'planner',
  reproducing: 'executor',
  executing: 'executor',
  verifying: 'verifier',
  reviewing: 'reviewer',
}

export type Phase = 'idle' | 'active' | 'waiting' | 'done' | 'failed' | 'budget' | 'cancelled'

export function phaseOf(state: TaskState | null): Phase {
  switch (state) {
    case null:
      return 'idle'
    case 'done':
    case 'pr_opened':
      return 'done'
    case 'failed':
      return 'failed'
    case 'budget_exceeded':
      return 'budget'
    case 'cancelled':
      return 'cancelled'
    case 'await_plan_approval':
    case 'await_pr_approval':
    case 'needs_human':
    case 'ci_watch':
      return 'waiting'
    default:
      return 'active'
  }
}

export function stateLabel(state: TaskState | null): string {
  return state ? STATE_LABEL[state] : ''
}

function uiRole(e: TwEvent): RoleId {
  const hint = e.payload.role_hint
  if (hint) return hint
  const r = e.role
  if (r === 'planner' || r === 'executor' || r === 'verifier' || r === 'reviewer') return r
  return 'system'
}

/** UTC → 北京时间 HH:MM */
export function bjClock(ts: string): string {
  const d = new Date(Date.parse(ts) + 8 * 3600_000)
  return `${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}`
}

/** 没有 display 时按 kind 自己拼一行 */
function fallbackText(e: TwEvent): string {
  switch (e.kind) {
    case 'task_started':
      return e.payload.issue_title
    case 'state_change':
      return STATE_LABEL[e.payload.to]
    case 'model_call':
      return `${e.payload.model}${e.payload.thinking ? ' · 思考' : ''}`
    case 'tool_call':
      return `$ ${e.payload.tool}${e.payload.ok ? '' : ` → ${e.payload.exit_code ?? '失败'}`}`
    case 'checkpoint':
      return e.payload.label
    case 'loop_warning':
      return `⚠ ${e.payload.signal}`
    case 'context_event':
      return e.payload.action === 'compact' ? '上下文压缩' : `上下文清理 ${e.payload.cleared ?? 0} 条`
    case 'hitl_request':
      return e.payload.question
    case 'hitl_response':
      return e.payload.answer
    case 'approval_requested':
      return `? ${e.payload.tool} ${e.payload.action}`
    case 'approval_resolved':
      return e.payload.decision === 'allow' ? '已允许' : '已拒绝'
    case 'mode_changed':
      return `模式 ${e.payload.from_mode} → ${e.payload.to_mode}`
    case 'verification':
      return `复验 ${e.payload.verdict}`
    case 'review':
      return `评审 ${e.payload.findings?.length ?? 0} 条`
    case 'task_finished':
      return STATE_LABEL[e.payload.status as TaskState] ?? e.payload.status
    case 'error':
      return `${e.payload.type}：${e.payload.message}`
  }
}

function toneOf(e: TwEvent): StreamTone {
  switch (e.kind) {
    case 'state_change':
      return 'chapter'
    case 'checkpoint':
      return 'divider'
    case 'tool_call':
      return e.payload.ok ? 'normal' : 'error'
    case 'model_call':
      return e.payload.peak ? 'warn' : 'normal'
    case 'loop_warning':
    case 'approval_requested':
      return 'warn'
    case 'mode_changed':
      return e.payload.risk === 'high' ? 'error' : 'chapter'
    case 'verification':
      return e.payload.verdict === 'pass' ? 'normal' : e.payload.verdict === 'fail' ? 'error' : 'warn'
    case 'error':
      return 'error'
    case 'task_finished':
      return 'final'
    default:
      return 'normal'
  }
}

/** 事件 → 推流行；未知 kind 返回 null（忽略） */
export function toStreamLine(e: AnyEvent): StreamLine | null {
  if (!isKnown(e)) return null
  const text = (e.payload.display ?? '').trim() || fallbackText(e)
  return { id: `e-${e.run_id}-${e.seq}`, seq: e.seq, role: uiRole(e), text, tone: toneOf(e) }
}

export interface RunView {
  runId: string | null
  title: string
  repo: string | null
  state: TaskState | null
  phase: Phase
  label: string
  activeRole: RoleId | null
  costCny: number
  cacheHitTokens: number
  cacheMissTokens: number
  peakCalls: number
  budgetCny: number
  messages: ChatMessage[]
  lastSeq: number
}

export const EMPTY_RUN: RunView = {
  runId: null,
  title: '',
  repo: null,
  state: null,
  phase: 'idle',
  label: '',
  activeRole: null,
  costCny: 0,
  cacheHitTokens: 0,
  cacheMissTokens: 0,
  peakCalls: 0,
  budgetCny: TASK_CAP_DEFAULT,
  messages: [],
  lastSeq: -1,
}

export function cacheHitRate(v: RunView): number | null {
  const total = v.cacheHitTokens + v.cacheMissTokens
  return total > 0 ? v.cacheHitTokens / total : null
}

/** 把一个事件折叠进 RunView（不可变） */
export function reduceRun(v: RunView, e: AnyEvent): RunView {
  if (e.seq <= v.lastSeq) return v // 重复 / 乱序重放：幂等
  const next: RunView = { ...v, lastSeq: e.seq, runId: v.runId ?? e.run_id }
  if (!isKnown(e)) return next

  const role = uiRole(e)
  if (role !== 'system') next.activeRole = role

  switch (e.kind) {
    case 'task_started': {
      const p = e.payload
      next.title = p.issue_number ? `#${p.issue_number} ${p.issue_title}` : p.issue_title
      next.repo = p.repo
      next.messages = [
        ...v.messages,
        { id: `m-${e.seq}`, role: 'user', content: p.issue_title, meta: p.repo, timestamp: bjClock(e.ts) },
      ]
      break
    }
    case 'state_change': {
      const to = e.payload.to
      next.state = to
      next.phase = phaseOf(to)
      next.label = STATE_LABEL[to]
      next.activeRole = STATE_ROLE[to] ?? (next.phase === 'active' ? next.activeRole : null)
      break
    }
    case 'model_call': {
      const u = e.payload.usage
      next.costCny = v.costCny + e.payload.cost_cny
      next.cacheHitTokens = v.cacheHitTokens + (u.cache_hit_tokens ?? 0)
      next.cacheMissTokens = v.cacheMissTokens + (u.cache_miss_tokens ?? 0)
      if (e.payload.peak) next.peakCalls = v.peakCalls + 1
      break
    }
    case 'task_finished': {
      const p = e.payload
      const terminal: TaskState =
        p.status === 'stuck' ? 'failed' : (p.status as TaskState)
      next.state = terminal
      next.phase = phaseOf(terminal)
      next.label = STATE_LABEL[terminal]
      next.activeRole = null
      const cr = p.cost_report
      if (cr) {
        next.costCny = cr.total_cny
        next.budgetCny = cr.budget_cny
      }
      const fr = p.finish_report
      const content = fr?.summary || (p.display ?? '').trim() || next.label
      const meta = [p.display, fr ? `置信度 ${fr.confidence.toFixed(2)}` : null].filter(Boolean).join(' · ')
      next.messages = [
        ...v.messages,
        { id: `m-${e.seq}`, role: 'assistant', content: content || next.label, meta, timestamp: bjClock(e.ts) },
      ]
      break
    }
    default:
      break
  }
  return next
}

export function foldRun(events: AnyEvent[], uptoSeq = Number.POSITIVE_INFINITY): RunView {
  let v = EMPTY_RUN
  for (const e of events) {
    if (e.seq > uptoSeq) break
    v = reduceRun(v, e)
  }
  return v
}
