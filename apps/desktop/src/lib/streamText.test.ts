import { describe, expect, it } from 'vitest'
import { nextShown, settledBoundary } from './streamText'

describe('流式正文', () => {
  it('段落边界不落在未闭合的代码块里', () => {
    expect(settledBoundary('一段')).toBe(0)
    expect(settledBoundary('甲\n\n乙')).toBe(3)
    const open = '甲\n\n```py\nx = 1\n\ny = 2'
    expect(settledBoundary(open)).toBe(3)
    const closed = '甲\n\n```py\nx\n```\n\n乙'
    expect(settledBoundary(closed)).toBe(closed.indexOf('乙'))
  })

  it('平滑追赶：至少 1 字，积压越多越快，不越界', () => {
    expect(nextShown(0, 5)).toBe(1)
    expect(nextShown(0, 1000)).toBe(120)
    expect(nextShown(990, 1000)).toBe(992)
    expect(nextShown(10, 10)).toBe(10)
    let s = 0
    let frames = 0
    while (s < 400) {
      s = nextShown(s, 400)
      frames++
    }
    expect(frames).toBeLessThan(60) // 400 字积压一秒内追上
  })
})
