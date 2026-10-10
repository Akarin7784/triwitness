import { beforeEach, describe, expect, it } from 'vitest'
import {
  addVersion,
  currentVersion,
  deleteChat,
  getChats,
  isVersionChild,
  reloadChats,
  renameChat,
  rootOf,
  selectVersion,
  versionAnchor,
  setFeedback,
  toggleStar,
} from './chats'

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
  reloadChats()
})

describe('会话层', () => {
  it('重命名 / 星标持久化', () => {
    renameChat('live:a', '  修复行数  ')
    toggleStar('live:a')
    reloadChats()
    expect(getChats().overlay['live:a']).toEqual({ title: '修复行数', starred: true })
    renameChat('live:a', '   ')
    expect(getChats().overlay['live:a'].title).toBeUndefined()
  })

  it('版本：重试 / 编辑追加并选中，可来回切换', () => {
    addVersion('fixture:success', 'live:b')
    addVersion('fixture:success', 'live:c')
    expect(currentVersion('fixture:success')).toBe('live:c')
    expect(rootOf('live:b')).toBe('fixture:success')
    expect(isVersionChild('live:b')).toBe(true)
    expect(isVersionChild('fixture:success')).toBe(false)
    selectVersion('fixture:success', 0)
    expect(currentVersion('fixture:success')).toBe('fixture:success')
    selectVersion('fixture:success', 99)
    expect(currentVersion('fixture:success')).toBe('live:c')
    expect(versionAnchor(getChats().versions['fixture:success'])).toBe('assistant')
    addVersion('fixture:success', 'live:d', 'edit')
    expect(versionAnchor(getChats().versions['fixture:success'])).toBe('user')
    expect(getChats().versions['fixture:success'].kinds).toEqual([null, 'retry', 'retry', 'edit'])
  })

  it('删除返回全部版本并隐藏', () => {
    addVersion('live:a', 'live:b')
    expect(deleteChat('live:a')).toEqual(['live:a', 'live:b'])
    expect(getChats().overlay['live:a'].deleted).toBe(true)
    expect(getChats().versions['live:a']).toBeUndefined()
  })

  it('反馈可设可清', () => {
    setFeedback('live:a', { rating: 'down', note: '没跑测试' })
    expect(getChats().feedback['live:a']).toEqual({ rating: 'down', note: '没跑测试' })
    setFeedback('live:a', null)
    expect(getChats().feedback['live:a']).toBeUndefined()
  })
})
