/**
 * 对话流（UI-20，照 Claude 的助手消息）：把事件折成一轮“用户 → 助手”，助手部分是有序的块：
 * 思考（reasoning_delta，可折叠）· 正文（model_delta，Markdown）· 工具行（tool_call，可展开）。
 * 没有增量的来源（fixture / 旧轨迹）用 model_call 的 display 补一段正文，界面一样。
 */
import { isKnown, type AnyEvent } from './events'
import { bjClock } from './mapEvent'

export interface ThinkingBlock {
  type: 'thinking'
  id: string
  callId: string
  text: string
  startMs: number
  endMs: number | null
}
export interface TextBlock {
  type: 'text'
  id: string
  callId: string
  text: string
  done: boolean
}
export interface ToolBlock {
  type: 'tool'
  id: string
  callId: string | null
  tool: string
  display: string
  ok: boolean
  exitCode: number | null
  durationMs: number
  args: string | null
  output: string | null
  permission: string | null
}
export type Block = ThinkingBlock | TextBlock | ToolBlock

export interface Turn {
  user: { text: string; time: string; repo: string | null } | null
  blocks: Block[]
  final: { text: string; meta: string; time: string; status: string } | null
  /** 最后一个块还在写（光标显示在这里） */
  streaming: boolean
}

export const EMPTY_TURN: Turn = { user: null, blocks: [], final: null, streaming: false }

const ms = (ts: string) => Date.parse(ts)

/** 不可变折叠；按 seq 有序调用。重复 / 乱序的事件由上游去重。 */
export function reduceTurn(t: Turn, e: AnyEvent): Turn {
  if (!isKnown(e)) return t
  switch (e.kind) {
    case 'task_started':
      return {
        ...t,
        user: { text: e.payload.issue_title, time: bjClock(e.ts), repo: e.payload.repo },
      }
    case 'reasoning_delta': {
      const { call_id, text } = e.payload
      const last = t.blocks[t.blocks.length - 1]
      if (last?.type === 'thinking' && last.callId === call_id && last.endMs === null) {
        return { ...t, streaming: true, blocks: [...t.blocks.slice(0, -1), { ...last, text: last.text + text }] }
      }
      const b: ThinkingBlock = { type: 'thinking', id: `th-${e.seq}`, callId: call_id, text, startMs: ms(e.ts), endMs: null }
      return { ...t, streaming: true, blocks: [...closeThinking(t.blocks, ms(e.ts)), b] }
    }
    case 'model_delta': {
      const { call_id, text } = e.payload
      const blocks = closeThinking(t.blocks, ms(e.ts))
      const last = blocks[blocks.length - 1]
      if (last?.type === 'text' && last.callId === call_id && !last.done) {
        return { ...t, streaming: true, blocks: [...blocks.slice(0, -1), { ...last, text: last.text + text }] }
      }
      return { ...t, streaming: true, blocks: [...blocks, { type: 'text', id: `tx-${e.seq}`, callId: call_id, text, done: false }] }
    }
    case 'model_call': {
      const p = e.payload
      if (p.role_hint === 'system' || e.role === 'summarizer') return t
      const callId = p.call_id ?? `seq-${e.seq}`
      let blocks = closeThinking(t.blocks, ms(e.ts)).map((b) =>
        b.type === 'text' && b.callId === callId && !b.done ? { ...b, done: true } : b,
      )
      const hasText = blocks.some((b) => b.type === 'text' && b.callId === callId)
      const hasDeltas = blocks.some((b) => b.callId === callId)
      // 没有增量（fixture / 非交互轨迹）：用 display 补一段正文；只是工具名列表（→ a、b）的不补
      if (!hasText && !hasDeltas && p.display && !p.display.startsWith('→')) {
        blocks = [...blocks, { type: 'text', id: `tx-${e.seq}`, callId, text: p.display, done: true }]
      }
      return { ...t, streaming: false, blocks }
    }
    case 'tool_call': {
      const p = e.payload
      const b: ToolBlock = {
        type: 'tool',
        id: `tl-${e.seq}`,
        callId: p.call_id ?? null,
        tool: p.tool,
        display: (p.display ?? '').trim() || p.tool,
        ok: p.ok,
        exitCode: p.exit_code ?? null,
        durationMs: p.duration_ms,
        args: p.args_preview ?? null,
        output: p.output_preview ?? null,
        permission: p.permission ?? null,
      }
      return { ...t, streaming: false, blocks: [...t.blocks, b] }
    }
    case 'task_finished': {
      const p = e.payload
      const fr = p.finish_report
      const text = fr?.summary || (p.display ?? '').trim()
      const meta = [p.display, fr ? `置信度 ${fr.confidence.toFixed(2)}` : null].filter(Boolean).join(' · ')
      return {
        ...t,
        streaming: false,
        blocks: closeThinking(t.blocks, ms(e.ts)).map((b) => (b.type === 'text' && !b.done ? { ...b, done: true } : b)),
        final: text ? { text, meta, time: bjClock(e.ts), status: p.status } : null,
      }
    }
    default:
      return t
  }
}

function closeThinking(blocks: Block[], at: number): Block[] {
  const i = blocks.length - 1
  const last = blocks[i]
  if (last?.type === 'thinking' && last.endMs === null) {
    return [...blocks.slice(0, i), { ...last, endMs: at }]
  }
  return blocks
}

export function foldTurn(events: readonly AnyEvent[]): Turn {
  let t = EMPTY_TURN
  for (const e of events) t = reduceTurn(t, e)
  return t
}

/** “思考了 N 秒”；不足 1 秒按 1 秒 */
export function thinkingSeconds(b: ThinkingBlock, now = Date.now()): number {
  return Math.max(1, Math.round(((b.endMs ?? now) - b.startMs) / 1000))
}

/** 工具行的人话标题：去掉推流里的 `$ ` 前缀 */
export function toolTitle(b: ToolBlock): string {
  return b.display.replace(/^\$\s*/, '')
}
