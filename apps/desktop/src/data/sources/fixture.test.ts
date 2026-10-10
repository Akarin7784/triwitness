import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { FixtureSource } from './fixture'
import { createMockSource, mockJsonl } from './mock'
import { parseJsonl, type AnyEvent } from '../events'
import { readFixture } from '../../test/fixtures'

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

const flush = () => vi.advanceTimersByTimeAsync(0)

describe('FixtureSource', () => {
  it('按 ts 差值与倍速回放全部事件，顺序不变', async () => {
    const text = readFixture('success')
    const src = new FixtureSource('success', async () => text, { speed: 2, maxGapMs: 1e9, leadMs: 0 })
    const got: AnyEvent[] = []
    src.subscribe((e) => got.push(e))
    await flush()
    expect(got.map((e) => e.seq)).toEqual([0])

    const all = parseJsonl(text)
    const spanMs = Date.parse(all.at(-1)!.ts) - Date.parse(all[0].ts)
    await vi.advanceTimersByTimeAsync(spanMs / 2 - 1)
    expect(got.length).toBeLessThan(all.length)
    await vi.advanceTimersByTimeAsync(2)
    expect(got.map((e) => e.seq)).toEqual(all.map((e) => e.seq))
    expect(src.afterSeq).toBe(all.at(-1)!.seq)
  })

  it('maxGapMs 限制长空白', async () => {
    const src = new FixtureSource('success', async () => readFixture('success'), { speed: 1, maxGapMs: 10, leadMs: 0 })
    const got: AnyEvent[] = []
    src.subscribe((e) => got.push(e))
    await vi.advanceTimersByTimeAsync(30 * 10 + 5)
    expect(got).toHaveLength(30)
  })

  it('afterSeq 续传只推送之后的事件', async () => {
    const src = new FixtureSource('failure', async () => readFixture('failure'), { maxGapMs: 1, leadMs: 0 })
    const got: number[] = []
    src.subscribe((e) => got.push(e.seq), { afterSeq: 15 })
    await vi.advanceTimersByTimeAsync(1000)
    expect(got).toEqual([16, 17, 18, 19])
  })

  it('退订与 close 之后不再推送', async () => {
    const src = new FixtureSource('success', async () => readFixture('success'), { maxGapMs: 100, leadMs: 0 })
    const a: number[] = []
    const b: number[] = []
    const unsub = src.subscribe((e) => a.push(e.seq))
    src.subscribe((e) => b.push(e.seq))
    await vi.advanceTimersByTimeAsync(150)
    unsub()
    const seenA = a.length
    await vi.advanceTimersByTimeAsync(300)
    expect(a).toHaveLength(seenA)
    src.close()
    const seenB = b.length
    await vi.advanceTimersByTimeAsync(10_000)
    expect(b).toHaveLength(seenB)
    expect(seenB).toBeLessThan(30)
  })

  it('坏行和未知 kind 不影响回放', async () => {
    const text = `${readFixture('budget_exceeded')}\nnot-json\n${JSON.stringify({
      v: 1, seq: 99, ts: '2026-10-10T14:30:29Z', task_id: 't', run_id: 'r', kind: 'model_delta', payload: {},
    })}`
    const src = new FixtureSource('x', async () => text, { maxGapMs: 1, leadMs: 0 })
    const got: number[] = []
    src.subscribe((e) => got.push(e.seq))
    await vi.advanceTimersByTimeAsync(1000)
    expect(got).toHaveLength(11)
    expect(got.at(-1)).toBe(99)
  })
})

describe('MockSource', () => {
  it('旧演示日志包装成合法的 tw-events/1', async () => {
    const events = parseJsonl(mockJsonl())
    expect(events[0].kind).toBe('task_started')
    expect(events.length).toBeGreaterThan(10)
    const src = createMockSource({ maxGapMs: 1, leadMs: 0 })
    const got: number[] = []
    src.subscribe((e) => got.push(e.seq))
    await vi.advanceTimersByTimeAsync(1000)
    expect(got).toEqual(events.map((e) => e.seq))
  })
})
