/**
 * tw-events/1 事件模型（类型由 schema 生成，见 tw-events.gen.ts）+ 宽松解析。
 * 规则（docs/design/event-protocol.md）：未知 kind 忽略；payload 未知字段忽略；坏行跳过不崩。
 */
import type { TaskState, TwEvents1 } from './tw-events.gen'

export type TwEvent = TwEvents1
export type TwKind = TwEvent['kind']
export type { TaskState }
export type {
  CostReport,
  FinishReport,
  ModelCallEvent,
  StateChangeEvent,
  TaskFinishedEvent,
  TaskStartedEvent,
  ToolCallEvent,
} from './tw-events.gen'

export const KNOWN_KINDS: ReadonlySet<string> = new Set<TwKind>([
  'task_started',
  'state_change',
  'model_call',
  'tool_call',
  'checkpoint',
  'loop_warning',
  'context_event',
  'hitl_request',
  'hitl_response',
  'approval_requested',
  'approval_resolved',
  'mode_changed',
  'model_delta',
  'reasoning_delta',
  'user_message',
  'turn_finished',
  'verification',
  'review',
  'task_finished',
  'error',
  'environment_prepared',
  'sandbox_progress',
])

/** 信封层面合法、但 kind 未知的事件：保留 seq 以便续传，渲染时忽略 */
export interface UnknownEvent {
  v?: number
  seq: number
  ts: string
  task_id: string
  run_id: string
  role?: string | null
  kind: string
  payload: Record<string, unknown>
  unknown: true
}

export type AnyEvent = TwEvent | UnknownEvent

export function isKnown(e: AnyEvent): e is TwEvent {
  return !('unknown' in e)
}

function isObj(x: unknown): x is Record<string, unknown> {
  return typeof x === 'object' && x !== null && !Array.isArray(x)
}

/** 解析一行；信封不合法返回 null */
export function parseEvent(line: string): AnyEvent | null {
  const text = line.trim()
  if (!text) return null
  let raw: unknown
  try {
    raw = JSON.parse(text)
  } catch {
    return null
  }
  if (!isObj(raw)) return null
  const { v, seq, ts, task_id, run_id, kind, payload } = raw
  if (v !== undefined && v !== 1) return null // 只读 v1；v2 是破坏性变更
  if (typeof seq !== 'number' || !Number.isInteger(seq) || seq < 0) return null
  if (typeof ts !== 'string' || Number.isNaN(Date.parse(ts))) return null
  if (typeof task_id !== 'string' || typeof run_id !== 'string') return null
  if (typeof kind !== 'string' || !isObj(payload)) return null
  if (!KNOWN_KINDS.has(kind)) {
    return { ...(raw as object), seq, ts, task_id, run_id, kind, payload, unknown: true } as UnknownEvent
  }
  return raw as unknown as TwEvent
}

/** 解析 JSONL；坏行跳过，按 seq 排序并去重 */
export function parseJsonl(text: string): AnyEvent[] {
  const seen = new Set<number>()
  const out: AnyEvent[] = []
  for (const line of text.split(/\r?\n/)) {
    const e = parseEvent(line)
    if (!e || seen.has(e.seq)) continue
    seen.add(e.seq)
    out.push(e)
  }
  return out.sort((a, b) => a.seq - b.seq)
}
