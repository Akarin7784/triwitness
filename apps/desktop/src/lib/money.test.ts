import { describe, expect, it } from 'vitest'
import { costTitle, fmtCny } from './money'

describe('结论卡金额（0.3.2：和账本对齐）', () => {
  it('小额显示四位，和账本一致', () => {
    expect(fmtCny(0.0161)).toBe('0.0161')
    expect(fmtCny(0.25)).toBe('0.250')
  })
  it('名义价与实付不同时悬停说明缓存命中', () => {
    expect(costTitle({ cost_cny: 0.0161, nominal_cost_cny: 0.021 })).toContain('0.0210')
    expect(costTitle({ cost_cny: 0.0161, nominal_cost_cny: 0.0161 })).not.toContain('名义价')
    expect(costTitle({ cost_cny: 0.0161 })).not.toContain('名义价')
  })
})
