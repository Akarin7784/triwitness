import type { AnyEvent } from '../events'
import { demoSession } from '../mock'
import { FixtureSource, type FixtureOptions } from './fixture'

/**
 * 把旧的演示日志包装成 tw-events/1（tool_call + display），走同一条渲染路径。
 * 只用于 ?source=mock。
 */
export function mockJsonl(): string {
  const base = Date.parse('2026-10-10T04:12:00Z')
  let t = base
  const lines: AnyEvent[] = [
    {
      v: 1,
      seq: 0,
      ts: new Date(t).toISOString(),
      task_id: 't_mock',
      run_id: 'r_mock',
      role: null,
      kind: 'task_started',
      payload: {
        display: 'Issue #87 · 演示',
        role_hint: 'system',
        issue_title: '修复登录态刷新竞态',
        repo: 'triwitness/core',
        config_hash: 'mock',
      },
    },
  ]
  demoSession.lines.forEach((l, i) => {
    t += (l.pauseBefore ?? 400) * 3
    const role = l.role === 'system' || l.role === 'user' ? null : l.role
    lines.push({
      v: 1,
      seq: i + 1,
      ts: new Date(t).toISOString(),
      task_id: 't_mock',
      run_id: 'r_mock',
      role,
      kind: 'tool_call',
      payload: {
        display: l.text,
        role_hint: l.role === 'user' ? 'system' : l.role,
        tool: 'bash',
        ok: true,
        duration_ms: 0,
      },
    })
  })
  return lines.map((e) => JSON.stringify(e)).join('\n')
}

export function createMockSource(opts?: FixtureOptions) {
  return new FixtureSource('mock', async () => mockJsonl(), opts)
}
