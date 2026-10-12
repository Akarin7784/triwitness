import { describe, expect, it } from 'vitest'
import { syncTerminal } from './statusSync'

const live = { phase: 'budget' as const, label: '触及安全上限', lastSeq: 40 }
describe('终态与书写同步', () => {
  it('最后一行写出前不显示终态', () => {
    const r = syncTerminal(live, { phase: 'active', label: '评审' }, 38, true)
    expect(r.phase).toBe('active')
    expect(r.label).toBe('评审')
  })
  it('写到最后一个事件后显示终态', () => {
    expect(syncTerminal(live, { phase: 'budget', label: '触及安全上限' }, 40, true)).toBe(live)
  })
  it('右栏不在时不等；非终态原样', () => {
    expect(syncTerminal(live, { phase: 'active', label: 'x' }, 0, false)).toBe(live)
    const act = { ...live, phase: 'active' as const }
    expect(syncTerminal(act, { phase: 'active', label: 'x' }, 0, true)).toBe(act)
  })
})
