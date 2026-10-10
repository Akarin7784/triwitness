import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { parseRules } from './rules'

describe('内置权限规则', () => {
  it('解析真实 configs/permissions.default.yaml', () => {
    const r = parseRules(readFileSync(new URL('../../../../configs/permissions.default.yaml', import.meta.url), 'utf8'))
    expect(r.deny.some((x) => x.rule === 'Read(**/.env)')).toBe(true)
    expect(r.deny.find((x) => x.rule === 'Read(**/.env.example)')?.exception).toBe(true)
    expect(r.ask.find((x) => x.rule === 'Bash(rm *)')?.backends).toEqual(['none'])
    expect(r.ask.some((x) => x.rule === 'Bash(git push *)')).toBe(true)
    expect(r.deny.length).toBeGreaterThan(20)
  })
})
