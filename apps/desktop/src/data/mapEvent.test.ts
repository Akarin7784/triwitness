import { describe, expect, it } from 'vitest'
import { parseJsonl, type AnyEvent } from './events'
import { bjClock, cacheHitRate, EMPTY_RUN, foldRun, reduceRun, toStreamLine } from './mapEvent'
import { readFixture } from '../test/fixtures'

const env = { v: 1 as const, ts: '2026-10-09T19:58:00Z', task_id: 't', run_id: 'r', role: null }

describe('toStreamLine', () => {
  it('优先使用 payload.display', () => {
    const l = toStreamLine({
      ...env,
      seq: 1,
      role: 'executor',
      kind: 'tool_call',
      payload: { display: '$ run_tests → 42 passed', tool: 'run_tests', ok: true, duration_ms: 10 },
    } as AnyEvent)
    expect(l).toMatchObject({ text: '$ run_tests → 42 passed', role: 'executor', tone: 'normal', seq: 1 })
  })

  it('context_event：上下文清理 / 压缩显示一行', () => {
    const l = toStreamLine({
      ...env,
      seq: 5,
      kind: 'context_event',
      payload: { action: 'clear', tokens_before: 80000, tokens_after: 30000, cleared: 6 },
    } as AnyEvent)
    expect(l?.text).toBe('上下文清理 6 条')
    expect(l?.tone).toBe('normal')
  })

  it('没有 display 时按 kind 拼一行', () => {
    const l = toStreamLine({
      ...env,
      seq: 2,
      kind: 'tool_call',
      payload: { tool: 'run_tests', ok: false, exit_code: 1, duration_ms: 10 },
    } as AnyEvent)
    expect(l?.text).toBe('$ run_tests → 1')
    expect(l?.tone).toBe('error')
  })

  it('role_hint 优先于 role；summarizer 等非四角色归为 system', () => {
    const hinted = toStreamLine({
      ...env,
      seq: 3,
      role: 'executor',
      kind: 'loop_warning',
      payload: { role_hint: 'system', signal: 'no_progress', level: 1 },
    } as AnyEvent)
    expect(hinted?.role).toBe('system')
    expect(hinted?.tone).toBe('warn')
    const other = toStreamLine({ ...env, seq: 4, role: 'summarizer', kind: 'checkpoint', payload: { label: '压缩' } } as AnyEvent)
    expect(other?.role).toBe('system')
    expect(other?.tone).toBe('divider')
  })

  it('状态切换是章节标记；未知 kind 被忽略', () => {
    const s = toStreamLine({ ...env, seq: 5, kind: 'state_change', payload: { from: 'received', to: 'planning' } } as AnyEvent)
    expect(s).toMatchObject({ text: '规划', tone: 'chapter' })
    const u = parseJsonl(JSON.stringify({ ...env, seq: 6, kind: 'model_delta', payload: {} }))[0]
    expect(toStreamLine(u)).toBeNull()
  })

  it('peak 的模型调用标为警示', () => {
    const l = toStreamLine({
      ...env,
      seq: 7,
      kind: 'model_call',
      payload: { model: 'deepseek-flash', thinking: false, usage: {}, cost_cny: 0.01, latency_ms: 1, peak: true },
    } as AnyEvent)
    expect(l?.tone).toBe('warn')
  })
})

describe('foldRun · golden fixtures', () => {
  it('success：完成、费用与命中率、首末两条对话', () => {
    const v = foldRun(parseJsonl(readFixture('success')))
    expect(v.phase).toBe('done')
    expect(v.label).toBe('完成')
    expect(v.title).toBe('#87 并发刷新 token 时偶发 401')
    expect(v.repo).toBe('example/auth-demo')
    expect(v.costCny).toBeCloseTo(0.085, 2)
    expect(cacheHitRate(v)).toBeGreaterThan(0.6)
    expect(v.messages.map((m) => m.role)).toEqual(['user', 'assistant'])
    expect(v.messages[1].content).toMatch(/单飞锁/)
    expect(v.messages[1].meta).toMatch(/置信度 0\.82/)
    expect(v.activeRole).toBeNull()
  })

  it('failure：失败态', () => {
    const v = foldRun(parseJsonl(readFixture('failure')))
    expect(v.phase).toBe('failed')
    expect(v.label).toBe('失败')
  })

  it('budget_exceeded：触及非金钱安全上限（0.3.2 起没有 ¥ 预算）', () => {
    const v = foldRun(parseJsonl(readFixture('budget_exceeded')))
    expect(v.phase).toBe('budget')
    expect(v.costCny).toBeGreaterThan(0)
    expect('budgetCny' in v).toBe(false)
    expect(v.messages.at(-1)?.content).toMatch(/安全上限/)
  })

  it('recorded（core 真实写出）：完成、标题、费用、执行者消息与流水', () => {
    const events = parseJsonl(readFixture('recorded'))
    const v = foldRun(events)
    expect(v.phase).toBe('done')
    expect(v.title).toBe('#12 parse_rows 遇到空列表时 IndexError')
    expect(v.repo).toBe('example/rows-demo')
    expect(v.costCny).toBeCloseTo(0.0151, 3)
    expect(cacheHitRate(v)).toBeCloseTo(0.9, 2)
    expect(v.messages.map((m) => m.role)).toEqual(['user', 'assistant'])
    expect(v.messages[1].content).toMatch(/空列表/)
    const lines = events.map(toStreamLine).filter((l) => l !== null)
    expect(lines.some((l) => l!.text.includes('run_tests → 1 failed'))).toBe(true)
  })

  it('只折叠到已写出的 seq：规划阶段点亮 planner', () => {
    const events = parseJsonl(readFixture('success'))
    const planning = events.find((e) => e.kind === 'state_change' && e.payload.to === 'planning')!
    const v = foldRun(events, planning.seq)
    expect(v.label).toBe('规划')
    expect(v.phase).toBe('active')
    expect(v.activeRole).toBe('planner')
    expect(v.messages).toHaveLength(1)
  })

  it('重复 / 回退的 seq 幂等', () => {
    const events = parseJsonl(readFixture('success'))
    const once = foldRun(events)
    const twice = events.reduce(reduceRun, once)
    expect(twice).toBe(once)
    expect(reduceRun(EMPTY_RUN, events[0]).lastSeq).toBe(0)
  })
})

describe('bjClock', () => {
  it('UTC → 北京时间', () => {
    expect(bjClock('2026-10-09T19:58:00Z')).toBe('03:58')
    expect(bjClock('2026-10-10T14:30:00Z')).toBe('22:30')
  })
})

describe('task_started.memory', () => {
  const started = (memory?: unknown) =>
    ({
      ...env,
      seq: 0,
      kind: 'task_started',
      payload: { issue_title: '修 bug', repo: 'o/r', config_hash: 'h', ...(memory === undefined ? {} : { memory }) },
    }) as AnyEvent

  it('没有 memory 字段（旧轨迹）/ null → run.memory 为 null', () => {
    expect(reduceRun(EMPTY_RUN, started()).memory).toBeNull()
    expect(reduceRun(EMPTY_RUN, started(null)).memory).toBeNull()
  })

  it('有记忆摘要 → 解析出事实与技能', () => {
    const v = reduceRun(
      EMPTY_RUN,
      started({ facts: [{ id: 'f1', text: '测试命令 uv run pytest', source: 'tw://run/r_1' }], skills: [{ name: 'fix-ci', version: 1 }], facts_total: 1, skills_total: 1 }),
    )
    expect(v.memory?.factsTotal).toBe(1)
    expect(v.memory?.skills[0].name).toBe('fix-ci')
  })
})
