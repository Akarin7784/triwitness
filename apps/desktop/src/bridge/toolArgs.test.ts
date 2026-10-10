import { describe, expect, it } from 'vitest'
import { toolArgsOk } from './toolArgs'

describe('toolArgsOk（与 Rust tool_args_ok 同表）', () => {
  it('放行固定子命令', () => {
    expect(toolArgsOk(['doctor', '--json'])).toBe(true)
    expect(toolArgsOk(['sandbox', 'install', 'wsl', '--yes'])).toBe(true)
    expect(toolArgsOk(['permissions', 'list', '--repo', 'C:/r'])).toBe(true)
    expect(toolArgsOk(['permissions', 'validate', '--kind', 'allow', '--rule', 'Bash(ls)'])).toBe(true)
    expect(toolArgsOk(['permissions', 'add', '--kind', 'deny', '--rule', 'Read(.env)', '--replace', 'x'])).toBe(true)
  })
  it('拒绝其他一切', () => {
    expect(toolArgsOk(['run', '--repo', 'x'])).toBe(false)
    expect(toolArgsOk(['sandbox', 'install', 'kernel', '--yes'])).toBe(false)
    expect(toolArgsOk(['permissions', 'remove', '--kind', 'deny', '--rule', 'x', '--replace', 'y'])).toBe(false)
    expect(toolArgsOk(['permissions', 'add', '--kind', 'god', '--rule', 'x'])).toBe(false)
    expect(toolArgsOk(['permissions', 'add', '--kind', 'allow', '--rule', '--live'])).toBe(false)
    expect(toolArgsOk(['permissions', 'add', '--kind', 'allow', '--kind', 'deny', '--rule', 'x'])).toBe(false)
    expect(toolArgsOk('doctor --json')).toBe(false)
  })
})
