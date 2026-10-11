import { describe, expect, it } from 'vitest'
import { choiceArgs, normalizeMode, UNRESTRICTED_PHRASE } from './choices'

describe('choiceArgs（与 Rust choice_args 同一张白名单）', () => {
  it('放行合法值，顺序固定', () => {
    expect(
      choiceArgs({ model: 'deepseek-flash', thinking: 'high', backend: 'none', maxCost: 0.5, permissionMode: 'ask', allowPeak: true }),
    ).toEqual(['--model', 'deepseek-flash', '--thinking', 'high', '--backend', 'none', '--max-cost', '0.50', '--permission-mode', 'ask', '--allow-peak'])
  })
  it('丢弃 v4-pro、越界上限、未知值', () => {
    expect(
      choiceArgs({ model: 'deepseek-v4-pro', thinking: 'ultra', backend: 'vm', maxCost: 9, permissionMode: 'root', allowPeak: false }),
    ).toEqual([])
    expect(choiceArgs({ maxCost: Number.NaN })).toEqual([])
    expect(choiceArgs({ maxCost: 0 })).toEqual([])
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
