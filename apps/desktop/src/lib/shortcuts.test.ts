import { describe, expect, it } from 'vitest'
import { SHORTCUTS, matchShortcut } from './shortcuts'

const ev = (key: string, o: { ctrl?: boolean; shift?: boolean; meta?: boolean; alt?: boolean; code?: string } = {}) => ({
  key,
  code: o.code ?? (key.length === 1 && /[a-z]/i.test(key) ? `Key${key.toUpperCase()}` : ''),
  ctrlKey: !!o.ctrl,
  metaKey: !!o.meta,
  shiftKey: !!o.shift,
  altKey: !!o.alt,
})

describe('快捷键（Claude 同款）', () => {
  it('全表都能匹配到自己的动作', () => {
    const cases: [ReturnType<typeof ev>, string][] = [
      [ev('O', { ctrl: true, shift: true }), 'newChat'],
      [ev('k', { ctrl: true }), 'search'],
      [ev('S', { ctrl: true, shift: true }), 'toggleSidebar'],
      [ev(',', { ctrl: true, code: 'Comma' }), 'settings'],
      [ev('/', { ctrl: true, code: 'Slash' }), 'shortcuts'],
      [ev('Escape'), 'stop'],
      [ev('Escape', { shift: true }), 'focusInput'],
      [ev('C', { ctrl: true, shift: true }), 'copyLast'],
      [ev('u', { ctrl: true }), 'upload'],
      [ev('I', { ctrl: true, shift: true }), 'modelMenu'],
      [ev('E', { ctrl: true, shift: true }), 'effortMenu'],
      [ev('}', { ctrl: true, shift: true, code: 'BracketRight' }), 'nextChat'],
      [ev('{', { ctrl: true, shift: true, code: 'BracketLeft' }), 'prevChat'],
      [ev('k', { meta: true }), 'search'],
    ]
    for (const [e, a] of cases) expect(matchShortcut(e), JSON.stringify(e)).toBe(a)
    const covered = new Set(cases.map((c) => c[1]))
    for (const s of SHORTCUTS) if (s.action !== 'send' && s.action !== 'newline') expect(covered.has(s.action)).toBe(true)
  })
  it('普通输入不触发', () => {
    expect(matchShortcut(ev('k'))).toBeNull()
    expect(matchShortcut(ev('k', { ctrl: true, alt: true }))).toBeNull()
    expect(matchShortcut(ev('Enter'))).toBeNull()
    expect(matchShortcut(ev('x', { ctrl: true }))).toBeNull()
    expect(matchShortcut(ev('Escape', { ctrl: true }))).toBeNull()
  })
})
