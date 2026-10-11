import { describe, expect, it } from 'vitest'
import { findEmptyChat } from './emptyChat'

const base = { messages: {}, draft: () => '', project: () => null, want: null }

describe('findEmptyChat（BUG3：连点新会话不再新建）', () => {
  it('有空会话就复用最新的', () => {
    expect(findEmptyChat([{ id: 'local:2' }, { id: 'local:1' }], base)).toBe('local:2')
  })
  it('有消息 / 有草稿 / 项目不同的不算空', () => {
    const locals = [{ id: 'local:3' }, { id: 'local:2' }, { id: 'local:1' }]
    expect(
      findEmptyChat(locals, {
        messages: { 'local:3': [{}] },
        draft: (id) => (id === 'local:2' ? '写了一半' : ''),
        project: (id) => (id === 'local:1' ? 'p1' : null),
        want: null,
      }),
    ).toBeNull()
    expect(findEmptyChat(locals, { ...base, project: (id) => (id === 'local:1' ? 'p1' : null), want: 'p1' })).toBe('local:1')
  })
  it('没有本地会话就返回 null（调用方新建）', () => {
    expect(findEmptyChat([], base)).toBeNull()
    expect(findEmptyChat([{ id: 'live:x' }], base)).toBeNull()
  })
})
