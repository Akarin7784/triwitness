import { useEffect, useState } from 'react'
import { parseJsonl } from '../data/events'
import { FIXTURE_NAMES, FIXTURES, type FixtureName } from '../data/sources/fixture'
import { bjClock, foldRun, type Phase } from '../data/mapEvent'

export interface RunEntry {
  id: FixtureName
  title: string
  phase: Phase
  label: string
  startedAt: string
  /** 开始时间（毫秒），会话列表按最近排序用 */
  at: number
}

/** 侧栏的会话列表：一次性读出 3 份 fixture 的标题、终态、开始时间（北京时间） */
export function useFixtureCatalog(): RunEntry[] {
  const [entries, setEntries] = useState<RunEntry[]>([])
  useEffect(() => {
    let alive = true
    Promise.all(
      FIXTURE_NAMES.map(async (id) => {
        const events = parseJsonl(await FIXTURES[id]())
        const v = foldRun(events)
        return { id, title: v.title, phase: v.phase, label: v.label, startedAt: events[0] ? bjClock(events[0].ts) : '', at: events[0] ? Date.parse(events[0].ts) || 0 : 0 }
      }),
    ).then((list) => alive && setEntries(list))
    return () => {
      alive = false
    }
  }, [])
  return entries
}
