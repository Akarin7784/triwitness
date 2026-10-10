import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Claude 式自动滚动：贴着底部时，内容一长就跟下去；用户往上翻就停下，并给出“回到底部”。
 * 内容高度变化用 ResizeObserver 监听（流式文字、展开块都算）。
 */
export function useStickToBottom<T extends HTMLElement, C extends HTMLElement>() {
  const scrollRef = useRef<T>(null)
  const contentRef = useRef<C>(null)
  const stuck = useRef(true)
  const [atBottom, setAtBottom] = useState(true)

  const toBottom = useCallback((smooth = true) => {
    const el = scrollRef.current
    if (!el) return
    stuck.current = true
    setAtBottom(true)
    el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' })
  }, [])

  useEffect(() => {
    const el = scrollRef.current
    const content = contentRef.current
    if (!el || !content) return
    let lastTop = el.scrollTop
    const onScroll = () => {
      const gap = el.scrollHeight - el.scrollTop - el.clientHeight
      if (el.scrollTop < lastTop - 2 && gap > 24) stuck.current = false // 用户往上翻
      if (gap < 24) stuck.current = true
      lastTop = el.scrollTop
      setAtBottom(gap < 24)
    }
    const ro = new ResizeObserver(() => {
      if (stuck.current) el.scrollTop = el.scrollHeight
      setAtBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 24)
    })
    el.addEventListener('scroll', onScroll, { passive: true })
    ro.observe(content)
    return () => {
      el.removeEventListener('scroll', onScroll)
      ro.disconnect()
    }
  }, [])

  return { scrollRef, contentRef, atBottom, toBottom }
}
