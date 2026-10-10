import { beforeEach, describe, expect, it } from 'vitest'
import {
  addKnowledge,
  createProject,
  deleteProject,
  getProjects,
  moveChat,
  projectOf,
  reloadProjects,
  removeKnowledge,
  setChatProject,
  updateProject,
} from './projects'
import { buildGuidance, stylePrompt } from './guidance'
import { DEFAULTS } from './prefs'

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
  reloadProjects()
})

describe('projects', () => {
  it('增删改、知识文件、会话归属', () => {
    const p = createProject('  三证  ', '桌面端')
    expect(p.name).toBe('三证')
    updateProject(p.id, { instructions: '提交信息用中文', name: '' })
    expect(getProjects().projects[0].name).toBe('未命名项目')
    addKnowledge(p.id, [{ name: 'a.md', path: '/x/a.md', size: 3 }])
    addKnowledge(p.id, [{ name: 'a.md', path: '/y/a.md', size: 4 }])
    expect(getProjects().projects[0].knowledge).toEqual([{ name: 'a.md', path: '/y/a.md', size: 4 }])
    setChatProject('local:1', p.id)
    moveChat('local:1', 'live:9')
    expect(projectOf('live:9')?.id).toBe(p.id)
    expect(projectOf('local:1')).toBeUndefined()
    setChatProject('live:9', 'nope')
    expect(projectOf('live:9')).toBeUndefined()
    setChatProject('live:9', p.id)
    removeKnowledge(p.id, '/y/a.md')
    expect(getProjects().projects[0].knowledge).toEqual([])
    deleteProject(p.id)
    expect(getProjects()).toEqual({ projects: [], chats: {} })
  })

  it('持久化', () => {
    createProject('A')
    reloadProjects()
    expect(getProjects().projects.map((p) => p.name)).toEqual(['A'])
  })
})

describe('guidance', () => {
  it('空设置 → 空串', () => {
    expect(buildGuidance(DEFAULTS)).toBe('')
    expect(stylePrompt(DEFAULTS)).toBeNull()
  })
  it('资料 + 风格 + 项目', () => {
    const p = createProject('三证')
    updateProject(p.id, { instructions: '用 pytest' })
    addKnowledge(p.id, [{ name: 'spec.md', path: '/s', size: 1 }])
    const g = buildGuidance(
      { ...DEFAULTS, name: 'Eva', about: '喜欢短回答', style: 'c1', customStyles: [{ id: 'c1', name: '诗意', prompt: '像写诗' }] },
      getProjects().projects[0],
    )
    expect(g).toContain('称呼：Eva')
    expect(g).toContain('### 回答风格（诗意）\n像写诗')
    expect(g).toContain('### 项目：三证\n用 pytest\n知识文件：spec.md（见附件）')
    expect(buildGuidance({ ...DEFAULTS, style: 'concise' })).toContain('简短')
  })
})
