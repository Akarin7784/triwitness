import { beforeEach, describe, expect, it } from 'vitest'
import { clearHistory, collectLocalData, exportFileStamp } from './localData'

class Mem implements Storage {
  m = new Map<string, string>()
  get length() {
    return this.m.size
  }
  clear() {
    this.m.clear()
  }
  getItem(k: string) {
    return this.m.get(k) ?? null
  }
  key(i: number) {
    return [...this.m.keys()][i] ?? null
  }
  removeItem(k: string) {
    this.m.delete(k)
  }
  setItem(k: string, v: string) {
    this.m.set(k, v)
  }
}

describe('localData', () => {
  beforeEach(() => {
    const s = new Mem()
    s.setItem('tw.chats', JSON.stringify({ overlay: { a: { title: 'x' } } }))
    s.setItem('tw.live.tasks', '[]')
    s.setItem('tw.prefs', JSON.stringify({ userName: 'Eva' }))
    s.setItem('tw.projects', '{"projects":[]}')
    s.setItem('other.app', 'secret-ish')
    Object.defineProperty(globalThis, 'localStorage', { value: s, configurable: true })
  })

  it('只导出 tw.* 条目', () => {
    const out = JSON.parse(collectLocalData(new Date('2026-10-11T00:00:00Z')))
    expect(Object.keys(out.data).sort()).toEqual(['tw.chats', 'tw.live.tasks', 'tw.prefs', 'tw.projects'])
    expect(out.data['tw.prefs'].userName).toBe('Eva')
    expect(JSON.stringify(out)).not.toContain('secret-ish')
  })

  it('清除会话记录，保留设置和项目', () => {
    expect(clearHistory()).toBe(2)
    expect(localStorage.getItem('tw.chats')).toBeNull()
    expect(localStorage.getItem('tw.prefs')).not.toBeNull()
    expect(localStorage.getItem('tw.projects')).not.toBeNull()
  })

  it('文件名带时间', () => {
    expect(exportFileStamp(new Date(2026, 9, 11, 9, 5))).toBe('triwitness-data-20261011-0905.json')
  })
})
