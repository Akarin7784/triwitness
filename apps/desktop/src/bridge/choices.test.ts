import { describe, expect, it } from 'vitest'
import { choiceArgs, UNRESTRICTED_PHRASE } from './choices'

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
  it('勇士模式必须带确认短语', () => {
    expect(choiceArgs({ permissionMode: 'unrestricted' })).toEqual([])
    expect(choiceArgs({ permissionMode: 'unrestricted', confirmUnrestricted: 'ok' })).toEqual([])
    expect(choiceArgs({ permissionMode: 'unrestricted', confirmUnrestricted: UNRESTRICTED_PHRASE })).toEqual([
      '--permission-mode',
      'unrestricted',
      '--confirm-unrestricted',
      UNRESTRICTED_PHRASE,
    ])
  })
})
