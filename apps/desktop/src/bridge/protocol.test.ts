import { describe, expect, it } from 'vitest'
import { approveCmd, CANCEL_CMD, parseBridgeLine } from './protocol'

describe('tw-bridge/1 行解析', () => {
  it('控制消息', () => {
    const r = parseBridgeLine('{"bridge":"hello","protocol":"tw-bridge/1","mode":"demo"}')
    expect(r).toEqual({ type: 'control', msg: { bridge: 'hello', protocol: 'tw-bridge/1', mode: 'demo' } })
  })

  it('事件行交给 tw-events/1 解析', () => {
    const line = JSON.stringify({
      v: 1,
      run_id: 'r1',
      task_id: 't1',
      seq: 3,
      ts: '2026-10-10T01:00:00Z',
      kind: 'approval_resolved',
      role: null,
      payload: { request_id: 'q1', decision: 'allow', scope: 'once', by: 'user', display: '已允许（一次）' },
    })
    const r = parseBridgeLine(line)
    expect(r?.type).toBe('event')
    expect(r?.type === 'event' && r.event.kind).toBe('approval_resolved')
  })

  it('杂项 / 坏行 / 未知控制返回 null', () => {
    expect(parseBridgeLine('')).toBeNull()
    expect(parseBridgeLine('Traceback (most recent call last):')).toBeNull()
    expect(parseBridgeLine('{bad json')).toBeNull()
    expect(parseBridgeLine('[1,2]')).toBeNull()
    expect(parseBridgeLine('{"bridge":"nope"}')).toBeNull()
    expect(parseBridgeLine('  {"bridge":"error","message":"x"}\r')).toEqual({
      type: 'control',
      msg: { bridge: 'error', message: 'x' },
    })
  })

  it('命令', () => {
    expect(JSON.parse(approveCmd('q1', 'allow', 'session'))).toEqual({
      cmd: 'approve',
      request_id: 'q1',
      decision: 'allow',
      scope: 'session',
    })
    expect(JSON.parse(approveCmd('q2', 'deny')).scope).toBe('once')
    expect(JSON.parse(CANCEL_CMD)).toEqual({ cmd: 'cancel' })
  })
})
