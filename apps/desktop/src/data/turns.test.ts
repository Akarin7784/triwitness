import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { parseBridgeLine } from '../bridge/protocol'
import { foldTurn, reduceTurn, thinkingSeconds, EMPTY_TURN, type ThinkingBlock } from './turns'
import { parseJsonl, type AnyEvent } from './events'

const events = (file: string): AnyEvent[] =>
  readFileSync(fileURLToPath(new URL(file, import.meta.url)), 'utf8')
    .split('\n')
    .map((l) => parseBridgeLine(l))
    .flatMap((p) => (p?.type === 'event' ? [p.event] : []))

/** 真实核心（--demo，思考强度 max）录下的一次流式运行 */
const STREAM = events('../bridge/__fixtures__/demo-stream.jsonl')

describe('对话流折叠', () => {
  it('思考 → 正文 → 工具行，按调用交错', () => {
    const t = foldTurn(STREAM)
    expect(t.user?.text).toContain('line_count')
    const kinds = t.blocks.map((b) => b.type)
    expect(kinds.slice(0, 3)).toEqual(['thinking', 'text', 'tool'])
    expect(kinds.filter((k) => k === 'tool').length).toBeGreaterThanOrEqual(7)
    const think = t.blocks[0] as ThinkingBlock
    expect(think.endMs).not.toBeNull()
    expect(thinkingSeconds(think)).toBeGreaterThanOrEqual(1)
    const md = t.blocks.find((b) => b.type === 'text' && b.text.includes('```python'))
    expect(md).toBeTruthy()
    const tool = t.blocks.find((b) => b.type === 'tool' && b.tool === 'read_file')
    expect(tool && tool.type === 'tool' && tool.args).toContain('verses.py')
    expect(t.final?.text).toContain('非空行')
    expect(t.streaming).toBe(false)
    expect(t.blocks.every((b) => b.type !== 'text' || b.done)).toBe(true)
  })

  it('流到一半：最后一块未完成、streaming=true', () => {
    const cut = STREAM.findIndex((e) => e.kind === 'model_delta') + 1
    const t = foldTurn(STREAM.slice(0, cut))
    expect(t.streaming).toBe(true)
    const last = t.blocks[t.blocks.length - 1]
    expect(last.type).toBe('text')
    expect(last.type === 'text' && last.done).toBe(false)
    // 正文一开始，思考块就收起（有结束时间）
    expect((t.blocks[0] as ThinkingBlock).endMs).not.toBeNull()
  })

  it('增量拼接与原文一致', () => {
    const t = foldTurn(STREAM)
    const firstCall = STREAM.find((e) => e.kind === 'model_delta')!
    const joined = STREAM.filter(
      (e) => e.kind === 'model_delta' && (e.payload as { call_id: string }).call_id === (firstCall.payload as { call_id: string }).call_id,
    )
      .map((e) => (e.payload as { text: string }).text)
      .join('')
    expect(t.blocks.find((b) => b.type === 'text')!.type === 'text' && (t.blocks.find((b) => b.type === 'text') as { text: string }).text).toBe(joined)
  })

  it('没有增量的 fixture：model_call 的 display 补成正文', async () => {
    const raw = readFileSync(fileURLToPath(new URL('../../../../evals/fixtures/events/success.jsonl', import.meta.url)), 'utf8')
    const t = foldTurn(parseJsonl(raw))
    expect(t.blocks.some((b) => b.type === 'text')).toBe(true)
    expect(t.blocks.some((b) => b.type === 'tool')).toBe(true)
    expect(t.blocks.some((b) => b.type === 'thinking')).toBe(false)
  })

  it('未知 kind 不影响', () => {
    const e = { ...STREAM[0], kind: 'future_kind' } as unknown as AnyEvent
    expect(reduceTurn(EMPTY_TURN, e)).toBe(EMPTY_TURN)
  })
})
