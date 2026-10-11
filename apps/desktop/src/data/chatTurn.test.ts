import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { beforeEach, describe, expect, it } from 'vitest'
import { parseBridgeLine, type ResultMsg } from '../bridge/protocol'
import { foldTurn } from './turns'
import { foldRun } from './mapEvent'
import type { AnyEvent } from './events'
import { parseSourceParam } from '../lib/sourceParam'
import { FIXTURE_NAMES } from './sources/fixture'
import { appendTurn, currentTurn, deleteChat, isThreadChild, reloadChats, rootOf, threadOf, addVersion } from '../lib/chats'

/** 真实核心 + 本机模拟服务（真实适配器 / SSE）录下的「你好」一轮（0.3.1 对话轮） */
const lines = readFileSync(fileURLToPath(new URL('../bridge/__fixtures__/chat-hello.jsonl', import.meta.url)), 'utf8')
  .split('\n')
  .map((l) => parseBridgeLine(l))
  .filter((x) => x !== null)
const events: AnyEvent[] = lines.flatMap((p) => (p.type === 'event' ? [p.event] : []))
const result = lines.flatMap((p) => (p.type === 'control' && p.msg.bridge === 'result' ? [p.msg as ResultMsg] : []))[0]

describe('对话轮：问候直接回复', () => {
  it('结果是 chat：只有回复，没有补丁 / 证据字段', () => {
    expect(result.kind).toBe('chat')
    expect(result.status).toBe('replied')
    expect(result.reply).toContain('你好')
    expect(result.verdict).toBeUndefined()
    expect(result.pr_md).toBeUndefined()
  })
  it('折成一轮：用户原话 + 思考 + 正文，结束后可复制 / 重试，没有工具行', () => {
    const t = foldTurn(events)
    expect(t.user?.text).toBe('你好')
    expect(t.kind).toBe('chat')
    expect(t.streaming).toBe(false)
    expect(t.final?.status).toBe('replied')
    expect(t.final?.text).toBe('')
    expect(t.blocks.map((b) => b.type)).toEqual(['thinking', 'text'])
    expect(t.blocks.some((b) => b.type === 'tool')).toBe(false)
  })
  it('状态签是「已回复」而不是任务完成', () => {
    const v = foldRun(events)
    expect(v.phase).toBe('done')
    expect(v.label).toBe('已回复')
    expect(v.title).toBe('你好')
    expect(v.verdict).toBeNull()
  })
})

describe('正式版没有演示 / 回放来源', () => {
  it('非开发构建默认打开新会话，不认 fixture / mock / stress', () => {
    expect(parseSourceParam('', false)).toMatch(/^local:\d+$/)
    expect(parseSourceParam('?source=mock', false)).toMatch(/^local:/)
    expect(parseSourceParam('?source=fixture:success', false)).toMatch(/^local:/)
    expect(parseSourceParam('?source=stress', false)).toMatch(/^local:/)
    expect(parseSourceParam('?source=live:abc-1', false)).toBe('live:abc-1')
  })
  it('开发构建（vitest）仍有 fixture 供测试', () => {
    expect(FIXTURE_NAMES.length).toBeGreaterThan(0)
  })
})

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

describe('多轮会话', () => {
  beforeEach(() => {
    ;(globalThis as { localStorage?: unknown }).localStorage = new Mem()
    reloadChats()
  })
  it('跟进追加一轮；重试只给最后一轮加版本；侧栏只列根', () => {
    appendTurn('live:a', 'live:b')
    appendTurn('live:a', 'live:c')
    expect(threadOf('live:a')).toEqual(['live:a', 'live:b', 'live:c'])
    expect(currentTurn('live:a')).toBe('live:c')
    addVersion('live:c', 'live:c2', 'retry')
    expect(currentTurn('live:a')).toBe('live:c2')
    expect(isThreadChild('live:b')).toBe(true)
    expect(isThreadChild('live:c2')).toBe(true)
    expect(isThreadChild('live:a')).toBe(false)
    expect(rootOf('live:c2')).toBe('live:a')
    expect(deleteChat('live:a').sort()).toEqual(['live:a', 'live:b', 'live:c', 'live:c2'])
    expect(threadOf('live:a')).toEqual(['live:a'])
  })
})
