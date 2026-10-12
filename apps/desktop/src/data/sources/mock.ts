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
        // 演示「本次用了哪些记忆」芯片（spec 013 §10 Q3）
        memory: {
          repo_key: 'github.com_triwitness_core',
          facts: [
            { id: 'm-1a2b3c4d', text: '测试命令：uv run pytest -q tests/auth（全量约 40s）', kind: 'test_cmd', source: 'tw://run/r_01M4K8BERZGNJWN07PV7PJB71C' }, // i18n-ignore: 演示数据
            { id: 'm-5e6f7a8b', text: 'token 刷新逻辑在 src/auth/session.py，锁用 asyncio.Lock', kind: 'layout', source: 'tw://run/r_01M4KEZZXH9M1VAEDJ7A4Y6MGR' }, // i18n-ignore: 演示数据
          ],
          skills: [{ name: 'async-race-repro', version: 2, description: '先用 asyncio.gather 写并发复现测试再修', source: 'tw://run/r_01M4KEZZXH9M1VAEDJ7A4Y6MGR' }], // i18n-ignore: 演示数据
          facts_total: 2,
          skills_total: 1,
          episodes: true,
        },
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
