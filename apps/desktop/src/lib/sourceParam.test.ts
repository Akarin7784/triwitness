import { describe, expect, it } from 'vitest'
import { parseSourceParam, speedParam } from './sourceParam'

describe('parseSourceParam', () => {
  it('默认 fixture:success', () => {
    expect(parseSourceParam('')).toBe('fixture:success')
    expect(parseSourceParam('?source=fixture:nope')).toBe('fixture:success')
  })
  it('识别 3 份 fixture 与 mock', () => {
    expect(parseSourceParam('?source=fixture:failure')).toBe('fixture:failure')
    expect(parseSourceParam('?source=fixture:budget_exceeded')).toBe('fixture:budget_exceeded')
    expect(parseSourceParam('?source=mock')).toBe('mock')
  })
  it('speed 只接受正数', () => {
    expect(speedParam('?speed=3')).toBe(3)
    expect(speedParam('?speed=-1')).toBeUndefined()
    expect(speedParam('')).toBeUndefined()
  })
})
