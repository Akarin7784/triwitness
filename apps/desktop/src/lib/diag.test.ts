import { describe, expect, it } from 'vitest'
import { diagArgs } from './diag'
import { toolArgsOk } from '../bridge/toolArgs'

describe('诊断包参数（与核心白名单一致）', () => {
  it('默认 / 指定运行都能过白名单；--out 与坏 id 不行', () => {
    expect(toolArgsOk(diagArgs())).toBe(true)
    expect(toolArgsOk(diagArgs('r_01M4NANDBP5J50KF7ESFJ0M7E3'))).toBe(true)
    expect(toolArgsOk(['diag', 'export', '--out', '/etc/x.zip', '--json'])).toBe(false)
    expect(toolArgsOk(diagArgs('../x'))).toBe(false)
  })
})
