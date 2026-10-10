import { useCallback, useEffect, useMemo, useState } from 'react'
import type { AnyEvent } from '../data/events'
import type { EventSource } from '../data/sources/types'
import { toStreamLine } from '../data/mapEvent'
import type { StreamLine } from '../types'

/** 把新事件并入列表：按 seq 去重、保序 */
export function mergeEvent(prev: AnyEvent[], e: AnyEvent): AnyEvent[] {
  if (prev.some((x) => x.seq === e.seq)) return prev
  const next = [...prev, e]
  return prev.length && prev[prev.length - 1].seq > e.seq ? next.sort((a, b) => a.seq - b.seq) : next
}

/**
 * 订阅一个 EventSource：收集事件，派生推流行。
 * key 变化或 restart() 时关闭旧源、从头订阅。factory 应是稳定引用（模块级函数）。
 */
export function useEventFeed<K extends string>(key: K, factory: (key: K) => EventSource | null) {
  const [epoch, setEpoch] = useState(0)
  // 事件按 (key, epoch) 归属；切换后旧数据自然失效，无需在 effect 里清空
  const [state, setState] = useState<{ tag: string; events: AnyEvent[] }>({ tag: '', events: [] })
  const tag = `${key}#${epoch}`

  useEffect(() => {
    const src = factory(key)
    if (!src) return
    const unsub = src.subscribe((e) =>
      setState((prev) => ({ tag, events: mergeEvent(prev.tag === tag ? prev.events : [], e) })),
    )
    return () => {
      unsub()
      src.close()
    }
  }, [key, tag, factory])

  const events = useMemo(() => (state.tag === tag ? state.events : []), [state, tag])
  const lines = useMemo(
    () => events.map(toStreamLine).filter((l): l is StreamLine => l !== null),
    [events],
  )
  const restart = useCallback(() => setEpoch((n) => n + 1), [])

  return { events, lines, restart }
}
