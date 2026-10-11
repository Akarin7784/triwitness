import { useCallback, useEffect, useMemo, useState } from 'react'
import type { AnyEvent } from '../data/events'
import type { EventSource } from '../data/sources/types'
import { toStreamLine } from '../data/mapEvent'
import type { StreamLine } from '../types'

/** 把新事件并入列表：按 seq 去重、保序 */
export function mergeEvent(prev: AnyEvent[], e: AnyEvent): AnyEvent[] {
  return mergeEvents(prev, [e])
}

/**
 * 一次并入一批事件（perf：每帧一次提交）。常见情形——批内有序且都比已有的新——走 O(批) 快路径；
 * 否则按 seq 去重后整体排序。没有新事件时返回原数组（引用不变，下游 memo 不重算）。
 */
export function mergeEvents(prev: AnyEvent[], batch: readonly AnyEvent[]): AnyEvent[] {
  if (!batch.length) return prev
  let lastSeq = prev.length ? prev[prev.length - 1].seq : -1
  let fast = true
  for (const e of batch) {
    if (e.seq <= lastSeq) {
      fast = false
      break
    }
    lastSeq = e.seq
  }
  if (fast) return prev.concat(batch)
  const seen = new Set(prev.map((x) => x.seq))
  const fresh: AnyEvent[] = []
  for (const e of batch) {
    if (seen.has(e.seq)) continue
    seen.add(e.seq)
    fresh.push(e)
  }
  if (!fresh.length) return prev
  return prev.concat(fresh).sort((a, b) => a.seq - b.seq)
}

/** 下一次提交的时机：可见时跟帧走（每帧最多一次），后台 / 隐藏时 rAF 不跑，改用低频定时器 */
function scheduleFlush(fn: () => void): () => void {
  if (typeof document !== 'undefined' && document.hidden) {
    const h = setTimeout(fn, 250)
    return () => clearTimeout(h)
  }
  const h = requestAnimationFrame(fn)
  return () => cancelAnimationFrame(h)
}

/** 推流行：增量映射（只映射新增事件），数组只在有新行时换引用 */
class LineFold {
  private events: readonly AnyEvent[] = []
  private lines: StreamLine[] = []
  map(events: readonly AnyEvent[]): StreamLine[] {
    const n = this.events.length
    const ext = n <= events.length && (n === 0 || (events[0] === this.events[0] && events[n - 1] === this.events[n - 1]))
    const from = ext ? n : 0
    const add: StreamLine[] = []
    for (let i = from; i < events.length; i++) {
      const l = toStreamLine(events[i])
      if (l) add.push(l)
    }
    this.lines = ext ? (add.length ? this.lines.concat(add) : this.lines) : add
    this.events = events
    return this.lines
  }
}

/**
 * 订阅一个 EventSource：收集事件，派生推流行。
 * 事件先进缓冲，按帧批量提交（一帧最多一次 setState），长回合 / 高速增量下不会每个 token 都重渲染。
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
    let buf: AnyEvent[] = []
    let cancel: (() => void) | null = null
    const flush = () => {
      cancel = null
      const batch = buf
      buf = []
      setState((prev) => {
        const base = prev.tag === tag ? prev.events : []
        const events = mergeEvents(base, batch)
        return events === base && prev.tag === tag ? prev : { tag, events }
      })
    }
    const unsub = src.subscribe((e) => {
      buf.push(e)
      cancel ??= scheduleFlush(flush)
    })
    // 切到后台时把排着的 rAF 换成定时器（rAF 在隐藏页面里不跑）
    const onVis = () => {
      if (!cancel) return
      cancel()
      cancel = scheduleFlush(flush)
    }
    document.addEventListener('visibilitychange', onVis)
    return () => {
      document.removeEventListener('visibilitychange', onVis)
      cancel?.()
      unsub()
      src.close()
    }
  }, [key, tag, factory])

  const events = useMemo(() => (state.tag === tag ? state.events : []), [state, tag])
  const [lineFold] = useState(() => new LineFold())
  const lines = useMemo(() => lineFold.map(events), [lineFold, events])
  const restart = useCallback(() => setEpoch((n) => n + 1), [])

  return { events, lines, restart }
}

