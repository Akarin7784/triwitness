import { describe, expect, it } from 'vitest'
import { dupOrdinals } from './dupOrdinals'

describe('同名会话序号', () => {
  const base = [
    { id: 'live:c', title: '#87', firstAt: 300, at: 300 },
    { id: 'live:a', title: '#87', firstAt: 100, at: 100 },
    { id: 'live:b', title: '#87', firstAt: 200, at: 200 },
    { id: 'live:x', title: '#12', firstAt: 50, at: 50 },
  ]
  it('按第一轮时间编号，非重名不编号', () => {
    const m = dupOrdinals(base)
    expect([m.get('live:a'), m.get('live:b'), m.get('live:c')]).toEqual([1, 2, 3])
    expect(m.has('live:x')).toBe(false)
  })
  it('新活动（at 变化、列表重排）不改序号', () => {
    const before = dupOrdinals(base)
    const after = dupOrdinals([{ ...base[1], at: 999 }, base[3], base[0], base[2]])
    expect(after).toEqual(before)
  })
})
