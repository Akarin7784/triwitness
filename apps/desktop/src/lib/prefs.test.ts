import { beforeEach, describe, expect, it } from 'vitest'

class Mem {
  m = new Map<string, string>()
  getItem(k: string) {
    return this.m.get(k) ?? null
  }
  setItem(k: string, v: string) {
    this.m.set(k, v)
  }
  removeItem(k: string) {
    this.m.delete(k)
  }
}

beforeEach(() => {
  ;(globalThis as { localStorage?: unknown }).localStorage = new Mem()
})

describe('偏好', () => {
  it('只允许 flash；v4-pro 永不可选也不在列表里', async () => {
    const p = await import('./prefs')
    expect(p.MODELS.some((m) => /v4-pro/i.test(m.id) || /v4-pro/i.test(m.name))).toBe(false)
    expect(p.MODELS.filter((m) => m.available).map((m) => m.id)).toEqual(['deepseek-flash'])
    expect(p.isSelectableModel('deepseek-v4-pro')).toBe(false)
    expect(p.isSelectableModel('qwen')).toBe(false)
    p.setPrefs({ model: 'deepseek-v4-pro' })
    expect(p.getPrefs().model).toBe('deepseek-flash')
    localStorage.setItem('tw.prefs', JSON.stringify({ model: 'deepseek-v4-pro', thinking: 'ultra' }))
    p.reloadPrefs()
    expect(p.getPrefs()).toMatchObject({ model: 'deepseek-flash', thinking: 'medium' })
  })

  it('思考档持久化，关掉后记得上一次的档位', async () => {
    const p = await import('./prefs')
    p.setPrefs({ thinking: 'high' })
    p.setPrefs({ thinking: 'off' })
    expect(p.getPrefs()).toMatchObject({ thinking: 'off', lastThinking: 'high' })
    p.reloadPrefs()
    expect(p.getPrefs().thinking).toBe('off')
  })

  it('草稿按会话保存', async () => {
    const p = await import('./prefs')
    p.setDraft('a', '你好')
    p.setDraft('b', 'x')
    p.setDraft('b', '')
    expect(p.getDraft('a')).toBe('你好')
    expect(p.getDraft('b')).toBe('')
  })
})

describe('设置（UI-21）', () => {
  it('坏值回默认；勇士模式不能从存储读出；0.3.2 去掉的预算设置被丢弃', async () => {
    const p = await import('./prefs')
    localStorage.setItem(
      'tw.prefs',
      JSON.stringify({ permissionMode: 'unrestricted', maxCost: 5, backend: 'vm', theme: 'neon', fontScale: 3, allowPeak: 'yes' }),
    )
    p.reloadPrefs()
    const s = p.getPrefs()
    expect(s.permissionMode).toBe('auto_review')
    expect('maxCost' in s).toBe(false)
    expect(s.backend).toBe('auto')
    expect(s.theme).toBe('light')
    expect(s.fontScale).toBe(1)
    expect('allowPeak' in s).toBe(false)
    expect(localStorage.getItem('tw.prefs') ?? '').not.toContain('maxCost') // 读入即迁移，不等下次写盘
    p.setPrefs({ permissionMode: 'unrestricted' as never, theme: 'dark' })
    expect(p.getPrefs().permissionMode).toBe('auto_review')
    expect(p.getPrefs().theme).toBe('dark')
    const saved = localStorage.getItem('tw.prefs') ?? ''
    expect(saved).not.toContain('maxCost')
    expect(saved).not.toContain('allowPeak')
  })

  it('勇士模式只上膛一次、不落盘', async () => {
    const p = await import('./prefs')
    p.armUnrestricted()
    expect(localStorage.getItem('tw.prefs') ?? '').not.toContain('unrestricted')
    expect(p.takeUnrestricted()).toBe(true)
    expect(p.takeUnrestricted()).toBe(false)
  })
})
