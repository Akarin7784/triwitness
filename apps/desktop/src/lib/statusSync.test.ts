import { describe, expect, it } from 'vitest'
import { finishedSeqOf, syncTerminal } from './statusSync'
import { foldRun, toStreamLine } from '../data/mapEvent'
import { parseJsonl } from '../data/events'
import { readFixture, type FixtureFile } from '../test/fixtures'

/**
 * 按真实回放顺序模拟（阿验 b2-r1）：事件逐个到达；每到一个事件，右栏把它对应的行从开始写到写完，
 * 写完且没有更多事件时 done = true（右栏「追上」了）。终态章节分隔线（state_change）→ … → 收尾行（task_finished，
 * 对话里的结论随同一事件出现）。要求：只有收尾行写完那一刻才翻终态。
 */
function timeline(name: FixtureFile) {
  const all = parseJsonl(readFixture(name))
  const steps: { seq: number; kind: string; stage: 'start' | 'done'; phase: string }[] = []
  let revealed = -1
  for (let n = 1; n <= all.length; n++) {
    const arrived = all.slice(0, n)
    const e = arrived[n - 1]
    const live = foldRun(arrived)
    const fin = finishedSeqOf(arrived)
    const hasLine = !!toStreamLine(e)
    if (hasLine) {
      // 笔尖进入新行：还没写完
      revealed = e.seq
      steps.push({ seq: e.seq, kind: e.kind, stage: 'start', phase: syncTerminal(live, { revealedSeq: revealed, done: false, shown: true }, '进行中', fin).phase })
    }
    // 这一行写完、等下一个事件：右栏已追上
    steps.push({ seq: e.seq, kind: e.kind, stage: 'done', phase: syncTerminal(live, { revealedSeq: revealed, done: true, shown: true }, '进行中', fin).phase })
  }
  return steps
}

describe('终态状态签与书写同步（真实回放顺序）', () => {
  for (const name of ['success', 'failure', 'budget_exceeded'] as const) {
    it(`${name}：终态分隔线写完、收尾行未写完都不翻；收尾行写完才翻`, () => {
      const steps = timeline(name)
      const TERM = ['done', 'failed', 'budget', 'cancelled', 'waiting']
      const first = steps.findIndex((s) => TERM.includes(s.phase))
      expect(first).toBe(steps.length - 1)
      expect(steps[first]).toMatchObject({ kind: 'task_finished', stage: 'done' })
      const divider = steps.filter((s) => s.kind === 'state_change' && s.stage === 'done').pop()
      expect(divider?.phase).toBe('active')
      expect(steps.find((s) => s.kind === 'task_finished' && s.stage === 'start')?.phase).toBe('active')
    })
  }
  it('右栏不在时不等；非终态原样', () => {
    const live = { phase: 'budget' as const, label: '触及安全上限', lastSeq: 9 }
    expect(syncTerminal(live, { revealedSeq: -1, done: false, shown: false }, '进行中', -1)).toBe(live)
    const act = { ...live, phase: 'active' as const }
    expect(syncTerminal(act, { revealedSeq: 0, done: false, shown: true }, '进行中', -1)).toBe(act)
  })
})
