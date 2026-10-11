import { describe, expect, it } from 'vitest'
import { prArgs } from './pr'
import { toolArgsOk } from '../bridge/toolArgs'

describe('开 PR 参数（与核心白名单一致）', () => {
  const run = 'r_01M4NANDBP5J50KF7ESFJ0M7E3'
  it('plan 不带 --yes，open 一定带 --yes；都能过白名单', () => {
    const plan = prArgs('plan', run, 'C:/src/verses')
    const open = prArgs('open', run, 'C:/src/verses', 'main')
    expect(plan).toEqual(['pr', 'plan', '--run', run, '--repo', 'C:/src/verses', '--json'])
    expect(open).toContain('--yes')
    expect(toolArgsOk(plan) && toolArgsOk(open)).toBe(true)
    expect(toolArgsOk(prArgs('plan', run))).toBe(true)
  })
})
