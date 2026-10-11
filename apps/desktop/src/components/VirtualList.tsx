import { Fragment, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from 'react'
import { ChatScrollContext } from '../lib/chatScroll'

export interface VirtualListProps<T> {
  items: readonly T[]
  itemKey: (item: T) => string
  /** 还没量过的条目的估计高度（px） */
  estimate: (item: T) => number
  render: (item: T, index: number) => ReactNode
  /** 条目数超过它才虚拟化；以下全量渲染（屏外块靠 .cv-auto 跳过布局 / 绘制） */
  threshold?: number
  /** 视口上下各多渲染多少像素 */
  overscan?: number
}

/**
 * 长回合的块列表（perf）：条目少时原样全量渲染；超过阈值后只挂载视口附近的条目，
 * 上下用占位撑高（量过的用真实高度，没量过的用估计）。
 * 贴底跟随 / 回到底部仍由 useStickToBottom 负责：它在内容变高时把 scrollTop 拉到底，滚动事件再驱动窗口跟到最新；
 * 往上翻时新挂载条目的高度差由浏览器的滚动锚定（overflow-anchor）吸收，不跳。
 * 应用内禁用了浏览器的 Ctrl+F（desktopGuards），查找走 Ctrl+K 的会话搜索；整条复制走消息操作条（读数据，不读 DOM）。
 */
export function VirtualList<T>(props: VirtualListProps<T>) {
  const scrollRef = useContext(ChatScrollContext)
  const { items, itemKey, render, threshold = 150 } = props
  if (!scrollRef || items.length <= threshold) {
    return <>{items.map((it, i) => <Fragment key={itemKey(it)}>{render(it, i)}</Fragment>)}</>
  }
  return <Windowed {...props} scrollRef={scrollRef} />
}

function Windowed<T>({
  items,
  itemKey,
  estimate,
  render,
  overscan = 1200,
  scrollRef,
}: VirtualListProps<T> & { scrollRef: RefObject<HTMLElement | null> }) {
  const listRef = useRef<HTMLDivElement>(null)
  const [heights, setHeights] = useState<ReadonlyMap<string, number>>(() => new Map())
  // 对话默认停在底部：先挂最后一屏，避免首帧从顶部渲染再跳
  const [range, setRange] = useState<[number, number]>(() => [Math.max(0, items.length - 40), items.length])

  const offsets = useMemo(() => {
    const off = new Float64Array(items.length + 1)
    for (let i = 0; i < items.length; i++) off[i + 1] = off[i] + (heights.get(itemKey(items[i])) ?? estimate(items[i]))
    return off
  }, [items, heights, itemKey, estimate])

  const offRef = useRef(offsets)
  useLayoutEffect(() => {
    offRef.current = offsets
  }, [offsets])

  const compute = useCallback(() => {
    const el = scrollRef.current
    const list = listRef.current
    const off = offRef.current
    if (!el || !list) return
    const n = off.length - 1
    const listTop = list.getBoundingClientRect().top - el.getBoundingClientRect().top + el.scrollTop
    const top = el.scrollTop - listTop - overscan
    const bottom = el.scrollTop - listTop + el.clientHeight + overscan
    let lo = 0
    let hi = n
    while (lo < hi) {
      const mid = (lo + hi) >> 1
      if (off[mid + 1] > top) hi = mid
      else lo = mid + 1
    }
    const start = Math.min(lo, Math.max(0, n - 1))
    let end = start
    while (end < n && off[end] < bottom) end++
    end = Math.max(end, Math.min(n, start + 1))
    setRange((r) => (r[0] === start && r[1] === end ? r : [start, end]))
  }, [scrollRef, overscan])

  // 滚动 / 视口尺寸变化：每帧最多算一次
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    let raf = 0
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(() => ((raf = 0), compute()))
    }
    const ro = new ResizeObserver(onScroll)
    ro.observe(el)
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      el.removeEventListener('scroll', onScroll)
    }
  }, [scrollRef, compute])

  // 条目增减 / 高度更新后重算窗口（贴底时据此跟到最新）
  useLayoutEffect(() => {
    compute()
  }, [offsets, compute])

  // 量高：一个 ResizeObserver 观察当前挂载的条目，一次回调合并成一次 setState
  const roRef = useRef<ResizeObserver | null>(null)
  const observed = useRef(new Set<Element>())
  useEffect(() => {
    const ro = new ResizeObserver((entries) => {
      setHeights((prev) => {
        let next: Map<string, number> | null = null
        for (const e of entries) {
          const key = (e.target as HTMLElement).dataset.vkey
          if (!key) continue
          const h = e.borderBoxSize?.[0]?.blockSize ?? (e.target as HTMLElement).offsetHeight
          if (h > 0 && Math.abs((prev.get(key) ?? -1) - h) > 0.5) (next ??= new Map(prev)).set(key, h)
        }
        return next ?? prev
      })
    })
    roRef.current = ro
    const seen = observed.current
    return () => {
      ro.disconnect()
      seen.clear()
      roRef.current = null
    }
  }, [])
  useLayoutEffect(() => {
    const ro = roRef.current
    const list = listRef.current
    if (!ro || !list) return
    const now = new Set<Element>(list.querySelectorAll(':scope > [data-vkey]'))
    for (const el of observed.current) if (!now.has(el)) ro.unobserve(el)
    for (const el of now) if (!observed.current.has(el)) ro.observe(el)
    observed.current = now
  })

  const [start, end] = [Math.min(range[0], items.length), Math.min(range[1], items.length)]
  const n = items.length
  return (
    <div ref={listRef} data-testid="virtual-list" data-virtual-range={`${start}-${end}/${n}`}>
      <div aria-hidden style={{ height: offsets[start] }} />
      {items.slice(start, end).map((it, i) => (
        <div key={itemKey(it)} className="v-item" data-vkey={itemKey(it)}>
          {render(it, start + i)}
        </div>
      ))}
      <div aria-hidden style={{ height: offsets[n] - offsets[end] }} />
    </div>
  )
}
