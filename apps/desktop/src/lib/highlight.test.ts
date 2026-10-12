import { describe, expect, it } from 'vitest'
import { highlightCode } from './highlight'

describe('代码高亮', () => {
  it('常用语言出 token、未知语言回退纯文本', () => {
    expect(highlightCode('def f(x):\n    return "a"', 'py')).toContain('hljs-keyword')
    expect(highlightCode('x', 'cobol')).toBeNull()
    expect(highlightCode('x', '')).toBeNull()
  })
  it('流式中途的半截代码也能高亮且已转义', () => {
    const h = highlightCode('const s = "<b>未闭合', 'ts')
    expect(h).toContain('hljs-keyword')
    expect(h).not.toContain('<b>')
  })
})
