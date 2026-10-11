import type { AnyEvent } from '../events'
import { FixtureSource, type FixtureOptions } from './fixture'

/**
 * 压测源（?source=stress&rounds=N&repeat=K）：合成一个很长的 agent 回合——每轮 = 思考增量 → 正文增量
 * （段落 / 列表 / 代码块；repeat=K 时一条正文重复 K 段，用来压超长单条回答）→ model_call 收口 → 工具调用。只用于性能测量与演示，不调模型、¥0。
 */
export function stressJsonl(rounds = 60, repeat = 1): string {
  const base = Date.parse('2026-10-11T06:00:00Z')
  let t = base
  let seq = 0
  const out: AnyEvent[] = []
  const env = { v: 1 as const, task_id: 't_stress', run_id: 'r_stress' }
  const push = (kind: string, payload: Record<string, unknown>, role: string | null = 'executor', dt = 40) => {
    t += dt
    out.push({ ...env, seq: seq++, ts: new Date(t).toISOString(), role, kind, payload } as unknown as AnyEvent)
  }
  push('task_started', { display: 'Stress · 长回合', role_hint: 'system', issue_title: '长回合压测：line_count 把空行也算进去了', repo: 'example/stress', config_hash: 'stress' }, null, 0) // i18n-ignore: 压测合成数据
  const think = '先确认复现路径：读 line_count 的实现，看空行是怎么被计入的。然后写一个最小复现，再动手修，最后跑回归。' // i18n-ignore: 压测合成数据
  const answer = (i: number) =>
    `第 ${i + 1} 步：我检查了 \`src/stats.py\` 里的计数逻辑，问题在于对 \`splitlines()\` 的结果没有过滤空白行。\n\n` + // i18n-ignore: 压测合成数据
    `- 复现：输入「床前明月光\\n\\n疑是地上霜」得到 3，应为 2\n- 影响：\`line_count\`、\`word_stats\` 两个入口\n- 方案：只统计 \`strip()\` 后非空的行\n\n` + // i18n-ignore: 压测合成数据
    '```python\ndef line_count(text: str) -> int:\n    return sum(1 for line in text.splitlines() if line.strip())\n```\n\n' +
    `接下来运行相关测试确认没有回归，然后继续第 ${i + 2} 步。` // i18n-ignore: 压测合成数据
  for (let i = 0; i < rounds; i++) {
    const call = `c${i}`
    for (let k = 0; k < think.length; k += 12) push('reasoning_delta', { call_id: call, index: k, text: think.slice(k, k + 12) }, 'executor', 30)
    const a = Array.from({ length: repeat }, (_, j) => answer(i * repeat + j)).join('\n\n')
    for (let k = 0; k < a.length; k += 8) push('model_delta', { call_id: call, index: k, text: a.slice(k, k + 8) }, 'executor', 25)
    push('model_call', { call_id: call, cost_cny: 0, latency_ms: 900, model: 'deepseek-flash', thinking: true, usage: {}, display: '→ run_tests' })
    push('tool_call', { display: `$ pytest tests/test_stats.py -q  # 第 ${i + 1} 轮`, role_hint: 'executor', tool: 'run_tests', ok: true, duration_ms: 1200, exit_code: 0, args_preview: 'tests/test_stats.py', output_preview: `${i + 3} passed in 0.4s` }) // i18n-ignore: 压测合成数据
  }
  push('task_finished', { display: '完成', role_hint: 'system', status: 'done' }, null) // i18n-ignore: 压测合成数据
  return out.map((e) => JSON.stringify(e)).join('\n')
}

export function createStressSource(rounds: number, opts?: FixtureOptions & { repeat?: number }) {
  return new FixtureSource('stress', async () => stressJsonl(rounds, opts?.repeat ?? 1), { maxGapMs: 400, ...opts })
}
