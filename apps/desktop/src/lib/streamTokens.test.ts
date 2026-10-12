import { describe, expect, it } from 'vitest'
import { tokenRanges } from './streamTokens'

describe('streamTokens', () => {
  it('增删统计和前面的文件名是同一个 token', () => {
    const t = '$ edit_file src/auth/session.py (+18 −4)'
    const [r] = tokenRanges(t)
    expect(t.slice(r[0], r[1])).toBe('src/auth/session.py (+18 −4)')
  })
  it('结果与 write_file 路径各自成 token', () => {
    const t = '$ run_tests tests/test_issue_87.py → 1 failed；$ write_file a/b.py'
    expect(tokenRanges(t).map(([a, b]) => t.slice(a, b))).toEqual(['tests/test_issue_87.py → 1 failed', '$ write_file a/b.py'])
  })
})

describe('streamTokens 全角括号', () => {
  it('全角括号、无空格的统计也和文件名粘在一起', () => {
    const t = '$ edit_file src/auth/session.py（+18 −4）'
    const [r] = tokenRanges(t)
    expect(t.slice(r[0], r[1])).toBe('src/auth/session.py（+18 −4）')
  })
})
