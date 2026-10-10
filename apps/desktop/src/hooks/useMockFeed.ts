import { useCallback, useEffect, useState } from 'react'
import type { StreamLine } from '../types'

/** 模拟 SSH / Agent 事件按块到达：前两行先到，其余每隔一段时间推送一行。 */
export function useMockFeed(source: StreamLine[], intervalMs = 1600) {
  const [count, setCount] = useState(2)
  const [epoch, setEpoch] = useState(0)

  useEffect(() => {
    if (count >= source.length) return
    const t = window.setTimeout(() => setCount((c) => c + 1), intervalMs)
    return () => window.clearTimeout(t)
  }, [count, source.length, intervalMs, epoch])

  const restart = useCallback(() => {
    setCount(source.length) // 重播时一次性交给书写引擎，由它控制节奏
    setEpoch((e) => e + 1)
  }, [source.length])

  return { lines: source.slice(0, count), restart }
}
