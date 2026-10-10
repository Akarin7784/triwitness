import { describe, expect, it } from 'vitest'
import { schedule } from './useWritingStream'
import type { StreamLine } from '../types'

const lines = [
  { id: 'a', role: 'executor', text: '复现成功。下一步：修复', pauseBefore: 100 },
  { id: 'b', role: 'verifier', text: '$ run_tests → 43 passed' },
] as unknown as StreamLine[]

describe('schedule（书写时序）', () => {
  it('确定性：同样输入得到同样时序', () => {
    expect(schedule(lines, 0, false)).toEqual(schedule(lines, 0, false))
  })

  it('时间单调递增，每个字一个落笔点，起点含 pauseBefore', () => {
    const { chars, endAt } = schedule(lines, 0, false)
    expect(chars).toHaveLength(Array.from(lines[0].text).length + Array.from(lines[1].text).length)
    expect(chars[0].at).toBe(100)
    for (let i = 1; i < chars.length; i++) expect(chars[i].at).toBeGreaterThanOrEqual(chars[i - 1].at)
    expect(endAt).toBeGreaterThan(chars[chars.length - 1].at)
  })

  it('句号后的停顿长于普通字间隔', () => {
    const { chars } = schedule(lines, 0, false)
    const i = chars.findIndex((c) => c.ch === '。')
    expect(chars[i + 1].at - chars[i].at).toBeGreaterThan(chars[1].at - chars[0].at)
  })

  it('reduced motion：整行同时出现，行间 120ms', () => {
    const { chars } = schedule(lines, 0, true)
    const a = chars.filter((c) => c.lineId === 'a').map((c) => c.at)
    const b = chars.filter((c) => c.lineId === 'b').map((c) => c.at)
    expect(new Set(a)).toEqual(new Set([120]))
    expect(new Set(b)).toEqual(new Set([240]))
  })

  it('追加：从给定起点继续排', () => {
    const first = schedule(lines.slice(0, 1), 0, false)
    const appended = schedule(lines.slice(1), first.endAt, false)
    expect(appended.chars[0].at).toBe(first.endAt)
  })
})
