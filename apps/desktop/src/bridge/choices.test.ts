import { describe, expect, it } from 'vitest'
import { choiceArgs, normalizeMode, UNRESTRICTED_PHRASE } from './choices'

describe('choiceArgs（与 Rust choice_args 同一张白名单）', () => {
  it('放行合法值，顺序固定', () => {
    expect(
      choiceArgs({ model: 'deepseek-flash', thinking: 'high', backend: 'none', permissionMode: 'ask' }),
    ).toEqual(['--model', 'deepseek-flash', '--thinking', 'high', '--backend', 'none', '--permission-mode', 'ask'])
  })
  it('丢弃 v4-pro、未知值；0.3.2 起旧的 maxCost / allowPeak 一律忽略', () => {
    expect(choiceArgs({ model: 'deepseek-v4-pro', thinking: 'ultra', backend: 'vm', permissionMode: 'root' })).toEqual([])
    expect(choiceArgs({ maxCost: 0.5, allowPeak: true })).toEqual([])
  })
  it('完全访问模式必须带确认短语（旧值 unrestricted 迁移）', () => {
    for (const m of ['full_access', 'unrestricted']) {
      expect(choiceArgs({ permissionMode: m })).toEqual([])
      expect(choiceArgs({ permissionMode: m, confirmUnrestricted: 'ok' })).toEqual([])
      expect(choiceArgs({ permissionMode: m, confirmUnrestricted: UNRESTRICTED_PHRASE })).toEqual([
        '--permission-mode',
        'full_access',
        '--confirm-full-access',
        UNRESTRICTED_PHRASE,
      ])
    }
  })
  it('旧值 auto_edit / auto 迁移为 auto_review', () => {
    for (const m of ['auto_edit', 'auto', 'auto_review']) expect(choiceArgs({ permissionMode: m })).toEqual(['--permission-mode', 'auto_review'])
    expect(normalizeMode('unrestricted')).toBe('full_access')
    expect(normalizeMode('root')).toBeUndefined()
  })
})
