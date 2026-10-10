import { describe, expect, it } from 'vitest'
import { isKnown, parseEvent, parseJsonl } from './events'
import { FIXTURE_FILES, readFixture } from '../test/fixtures'

const base = { v: 1, seq: 3, ts: '2026-10-10T02:41:07Z', task_id: 't_1', run_id: 'r_1', role: null }

describe('parseEvent', () => {
  it('解析合法的已知事件', () => {
    const e = parseEvent(JSON.stringify({ ...base, kind: 'checkpoint', payload: { label: 'x' } }))
    expect(e && isKnown(e) && e.kind).toBe('checkpoint')
  })

  it('坏行返回 null 而不是抛错', () => {
    expect(parseEvent('{not json')).toBeNull()
    expect(parseEvent('')).toBeNull()
    expect(parseEvent('[]')).toBeNull()
    expect(parseEvent(JSON.stringify({ ...base, seq: -1, kind: 'error', payload: {} }))).toBeNull()
    expect(parseEvent(JSON.stringify({ ...base, ts: 'yesterday', kind: 'error', payload: {} }))).toBeNull()
    expect(parseEvent(JSON.stringify({ ...base, kind: 'error' }))).toBeNull()
  })

  it('拒绝 v2（破坏性版本）', () => {
    expect(parseEvent(JSON.stringify({ ...base, v: 2, kind: 'error', payload: {} }))).toBeNull()
  })

  it('未知 kind 保留为 UnknownEvent', () => {
    const e = parseEvent(JSON.stringify({ ...base, kind: 'model_delta', payload: { text: 'hi' } }))
    expect(e).not.toBeNull()
    expect(isKnown(e!)).toBe(false)
    expect(e!.seq).toBe(3)
  })
})

describe('parseJsonl', () => {
  it('跳过坏行、按 seq 去重排序', () => {
    const line = (seq: number) => JSON.stringify({ ...base, seq, kind: 'checkpoint', payload: { label: String(seq) } })
    const out = parseJsonl([line(2), 'garbage', line(0), line(2), '', line(1)].join('\n'))
    expect(out.map((e) => e.seq)).toEqual([0, 1, 2])
  })

  it.each(FIXTURE_FILES)('golden fixture %s：全部可解析、seq 从 0 连续、都是已知 kind', (name) => {
    const text = readFixture(name)
    const rows = text.trim().split('\n').length
    const events = parseJsonl(text)
    expect(events).toHaveLength(rows)
    expect(events.map((e) => e.seq)).toEqual([...Array(rows).keys()])
    expect(events.every(isKnown)).toBe(true)
    expect(events[0].kind).toBe('task_started')
    expect(events.at(-1)!.kind).toBe('task_finished')
  })
})
