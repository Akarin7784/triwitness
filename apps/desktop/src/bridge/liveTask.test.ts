import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { LiveTask, prSummary } from './liveTask'
import { foldRun, toStreamLine } from '../data/mapEvent'
import type { AnyEvent } from '../data/events'

/** 真实核心录下的一次演示任务（tw run --demo --jsonl，含一次审批 → 允许一次） */
const LINES = readFileSync(fileURLToPath(new URL('./__fixtures__/demo-run.jsonl', import.meta.url)), 'utf8')
  .split('\n')
  .filter(Boolean)

describe('LiveTask：回放录制的核心输出（e2e replay）', () => {
  it('审批卡出现 → 结案 → 结论', () => {
    const t = new LiveTask('x')
    const seen: AnyEvent[] = []
    t.subscribe((e) => seen.push(e))
    let sawCard = false
    for (const line of LINES) {
      t.push(line)
      if (t.snapshot.approvals.length) {
        sawCard = true
        expect(t.snapshot.approvals[0].action).toContain('unittest')
      }
    }
    expect(sawCard).toBe(true)
    const s = t.snapshot
    expect(s.mode).toBe('demo')
    expect(s.runId).toMatch(/^r_/)
    expect(s.runDir).toContain('runs')
    expect(s.approvals).toEqual([])
    expect(Object.values(s.resolved)[0]).toContain('已允许')
    expect(s.result?.status).toBe('done')
    expect(s.result?.verdict).toBe('pass')
    expect(s.result?.risk_level).toMatch(/^L[0-3]$/)
    expect(s.result?.cost_cny).toBe(0)

    // 推流 / 折叠走原有路径：每个已知事件都有一行，状态折到“已完成”
    expect(seen.length).toBe(t.allEvents.length)
    expect(seen.every((e) => toStreamLine(e) !== null)).toBe(true)
    const run = foldRun(seen)
    expect(run.state).toBe('done')
    expect(run.verdict).toBe('pass')
    expect(run.approvalsPending).toBe(0)
    expect(run.costCny).toBe(0)
  })

  it('跟笔：折叠到审批那一行时状态签应为待批', () => {
    const t = new LiveTask('x')
    for (const l of LINES) t.push(l)
    const req = t.allEvents.find((e) => e.kind === 'approval_requested')!
    expect(foldRun([...t.allEvents], req.seq).approvalsPending).toBe(1)
  })

  it('重复行幂等；后订阅者从 afterSeq 续上', () => {
    const t = new LiveTask('x')
    for (const l of LINES) t.push(l)
    for (const l of LINES) t.push(l)
    const n = t.allEvents.length
    expect(new Set(t.allEvents.map((e) => e.seq)).size).toBe(n)
    const late: AnyEvent[] = []
    t.subscribe((e) => late.push(e), { afterSeq: t.allEvents[n - 3].seq })
    expect(late.length).toBe(2)
  })

  it('退出 / 出错清掉悬而未决的审批', () => {
    const t = new LiveTask('x')
    const upto = LINES.findIndex((l) => l.includes('"approval_requested"'))
    for (const l of LINES.slice(0, upto + 1)) t.push(l)
    expect(t.snapshot.approvals.length).toBe(1)
    let calls = 0
    t.watch(() => calls++)
    t.exit(1)
    expect(t.snapshot.approvals).toEqual([])
    expect(t.snapshot.exited).toBe(true)
    expect(calls).toBe(1)
  })

  it('pr.md 摘要', () => {
    expect(prSummary(null)).toEqual([])
    expect(prSummary('# 标题\n\n<!-- x -->\n- a\n- b\n', 2)).toEqual(['# 标题', '- a'])
  })
})
