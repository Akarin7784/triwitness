/**
 * 本次运行用了哪些记忆（spec 013 §10 Q3）：读 task_started.payload.memory（core 摘要，可能缺省 / 为 null / 字段不全）。
 * 宽松解析：缺字段一律忽略；没有任何事实 / 技能时返回 null（界面不显示芯片）。
 */

export interface MemoryFact {
  id: string
  text: string
  kind: string | null
  source: string | null
}

export interface MemorySkill {
  name: string
  version: number | null
  description: string
  source: string | null
}

export interface MemoryUsed {
  repoKey: string | null
  facts: MemoryFact[]
  skills: MemorySkill[]
  factsTotal: number
  skillsTotal: number
  /** Planner 会按 Issue 检索经验片段（命中的条目在 artifacts/memory.json） */
  episodes: boolean
}

const str = (v: unknown): string | null => (typeof v === 'string' && v.trim() ? v : null)
const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null)
const rec = (v: unknown): Record<string, unknown> | null =>
  v && typeof v === 'object' && !Array.isArray(v) ? (v as Record<string, unknown>) : null

export function parseMemory(raw: unknown): MemoryUsed | null {
  const m = rec(raw)
  if (!m) return null
  const facts: MemoryFact[] = (Array.isArray(m.facts) ? m.facts : [])
    .map(rec)
    .filter((f): f is Record<string, unknown> => !!f && !!str(f.text))
    .map((f, i) => ({ id: str(f.id) ?? `f${i}`, text: str(f.text)!, kind: str(f.kind), source: str(f.source) }))
  const skills: MemorySkill[] = (Array.isArray(m.skills) ? m.skills : [])
    .map(rec)
    .filter((s): s is Record<string, unknown> => !!s && !!str(s.name))
    .map((s) => ({ name: str(s.name)!, version: num(s.version), description: str(s.description) ?? '', source: str(s.source) }))
  const factsTotal = Math.max(num(m.facts_total) ?? 0, facts.length)
  const skillsTotal = Math.max(num(m.skills_total) ?? 0, skills.length)
  if (factsTotal === 0 && skillsTotal === 0) return null
  return { repoKey: str(m.repo_key), facts, skills, factsTotal, skillsTotal, episodes: m.episodes === true }
}

/** tw://run/<id> → 短运行号（r_01M4…最后 6 位），其他来源原样 */
export function shortSource(src: string | null): string | null {
  if (!src) return null
  const run = /^tw:\/\/run\/(.+)$/.exec(src)
  if (!run) return src
  const id = run[1]
  return id.length > 10 ? `${id.slice(0, 3)}…${id.slice(-6)}` : id
}
