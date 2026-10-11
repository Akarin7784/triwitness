import { describe, expect, it, vi } from 'vitest'

vi.mock('./coreTool', () => ({ coreTool: vi.fn() }))

describe('真实账本（v0.3）', () => {
  it('核心返回 JSON → ok；未连接 → offline；出错 → error（不编数字）', async () => {
    const { coreTool } = await import('./coreTool')
    const m = vi.mocked(coreTool)
    const l = await import('./ledger')
    expect(l.getLedgerState().status).toBe('loading')
    m.mockResolvedValueOnce({ ok: true, data: { spent: 1.5, total_cny: 100, remaining: 98.5, recent: [] } as never })
    await l.refreshLedger()
    expect(m).toHaveBeenCalledWith(['budget', '--json'])
    const s = l.getLedgerState()
    expect(s.status === 'ok' && s.data.remaining).toBe(98.5)
    m.mockResolvedValueOnce({ ok: false, error: 'x', offline: true })
    await l.refreshLedger()
    expect(l.getLedgerState().status).toBe('offline')
    m.mockResolvedValueOnce({ ok: false, error: 'boom' })
    await l.refreshLedger()
    expect(l.getLedgerState()).toEqual({ status: 'error', error: 'boom' })
  })

  it('命中率', async () => {
    const l = await import('./ledger')
    expect(l.hitRate({ input_tokens: 0, cache_hit_tokens: 0 })).toBeNull()
    expect(l.hitRate({ input_tokens: 100, cache_hit_tokens: 96 })).toBeCloseTo(0.96)
  })
})
