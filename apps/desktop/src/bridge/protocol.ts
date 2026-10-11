/**
 * tw-bridge/1（UI-10）：桌面端 ↔ Python 核心（`tw run --jsonl`）。见 src/triwitness/bridge/stdio.py。
 * 核心 stdout 每行一个 JSON：tw-events/1 事件，或带 `bridge` 字段的控制消息。
 */
import { parseEvent, type AnyEvent } from '../data/events'

export const PROTOCOL = 'tw-bridge/1'

/** 正式版只有 live；demo / replay 仅开发桥（import.meta.env.DEV）可选 */
export type CoreMode = 'demo' | 'replay' | 'live'
export type Verdict = 'pass' | 'fail' | 'inconclusive'
export type RiskLevel = 'L0' | 'L1' | 'L2' | 'L3'
export type ApprovalScope = 'once' | 'session' | 'always'

export interface HelloMsg {
  bridge: 'hello'
  protocol: string
  mode: CoreMode
}
export interface RunMsg {
  bridge: 'run'
  run_id: string
  task_id: string
  run_dir: string
}
export interface ResultMsg {
  bridge: 'result'
  /** 0.3.1 对话轮：chat = 直接回复（没有补丁 / 证据，下面的任务字段都缺省）；task = 本轮转成了仓库任务 */
  kind?: 'chat' | 'task'
  reply?: string | null
  run_id?: string
  status: string
  run_dir: string
  branch: string | null
  backend: string
  /** 实付（与账本一致；本地缓存命中不计费） */
  cost_cny: number
  /** 名义价（含本地缓存命中，按 usage 计）；0.3.2 起 */
  nominal_cost_cny?: number
  steps: number
  reason: string | null
  summary: string | null
  verdict: Verdict | null
  risk_level: RiskLevel | null
  clean_env: 'verified' | 'failed' | 'unverified' | null
  pr_md: string | null
  /** 本地仓库路径（开 PR 用；0.3.2 起） */
  repo?: string | null
}
export interface ErrorMsg {
  bridge: 'error'
  message: string
  /** budget：触及非金钱安全上限（轮数 / 时间 / token 兜底）；0.3.2 起不再有 peak_blocked */
  code?: 'budget' | string
}
export interface AckMsg {
  bridge: 'ack'
  cmd: string | null
  ok: boolean
  request_id?: string
  error?: string
}
export type ControlMsg = HelloMsg | RunMsg | ResultMsg | ErrorMsg | AckMsg

export type BridgeLine = { type: 'event'; event: AnyEvent } | { type: 'control'; msg: ControlMsg }

const CONTROL = new Set(['hello', 'run', 'result', 'error', 'ack'])

/** 一行 → 事件 / 控制消息；不认识的行返回 null（容忍核心打印的杂项） */
export function parseBridgeLine(line: string): BridgeLine | null {
  const text = line.trim()
  if (!text.startsWith('{')) return null
  let raw: unknown
  try {
    raw = JSON.parse(text)
  } catch {
    return null
  }
  if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) return null
  const b = (raw as { bridge?: unknown }).bridge
  if (typeof b === 'string') return CONTROL.has(b) ? { type: 'control', msg: raw as ControlMsg } : null
  const event = parseEvent(text)
  return event ? { type: 'event', event } : null
}

export function approveCmd(requestId: string, decision: 'allow' | 'deny', scope: ApprovalScope = 'once'): string {
  return JSON.stringify({ cmd: 'approve', request_id: requestId, decision, scope })
}

export const CANCEL_CMD = JSON.stringify({ cmd: 'cancel' })
