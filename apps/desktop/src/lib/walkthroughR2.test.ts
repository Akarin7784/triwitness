import { describe, expect, it } from 'vitest'
import { closeOpenMarkdown, middlePath } from './streamText'

describe('走查 r2', () => {
  it('补齐未闭合行内代码', () => {
    expect(closeOpenMarkdown('看起来 `fetch')).toBe('看起来 `fetch`')
    expect(closeOpenMarkdown('看起来 `')).toBe('看起来 ')
    expect(closeOpenMarkdown('`a` 和 `b`')).toBe('`a` 和 `b`')
    expect(closeOpenMarkdown('**粗')).toBe('**粗**')
    expect(closeOpenMarkdown('```ts\nconst a')).toBe('```ts\nconst a\n```')
  })
  it('长路径中间省略且保留文件名', () => {
    const p = 'src/very/long/nested/directory/structure/auth/login_refresh.ts'
    const m = middlePath(p)
    expect(m.length).toBeLessThanOrEqual(30)
    expect(m).toContain('…')
    expect(m.endsWith('refresh.ts')).toBe(true)
    expect(middlePath('a/b.ts')).toBe('a/b.ts')
  })
})
