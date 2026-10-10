import { useEffect, useState } from 'react'
import { useReducedMotion } from '../hooks/useReducedMotion'
import { Markdown } from './Markdown'
import { nextShown, settledBoundary } from '../lib/streamText'

const SEG = 6 // 尾段按 6 字一段淡入

/**
 * Claude 式流式正文：文字按帧平滑追上目标，新写出的片段轻轻淡入，结尾一个呼吸的软光标；
 * 已成段落的部分即时渲染为 Markdown。挂载时就已完成的消息（历史）直接整段显示，不播动画。
 */
export function StreamingText({ text, streaming }: { text: string; streaming: boolean }) {
  const reduced = useReducedMotion()
  const [animate] = useState(streaming) // 挂载时是否在写：决定播不播动画（之后不变）
  const [shown, setShown] = useState(() => (animate ? 0 : text.length))
  const target = reduced || !animate ? text.length : shown

  useEffect(() => {
    if (reduced || !animate) return
    let raf = 0
    const tick = () => {
      setShown((s) => {
        const n = nextShown(s, text.length)
        if (n < text.length) raf = requestAnimationFrame(tick)
        return n
      })
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [text, reduced, animate])

  const visible = text.slice(0, target)
  const writing = streaming || target < text.length
  if (!writing) return <Markdown text={text} />

  const cut = settledBoundary(visible)
  const head = visible.slice(0, cut)
  const tail = visible.slice(cut)
  // 尾段里有 Markdown 标记（代码块 / 列表 / 行内代码 / 粗体）就直接按 Markdown 渲染，避免露出原始符号
  const openFence = /```|`|\*\*|^\s*([-*]|\d+\.)\s|^#{1,3}\s/m.test(tail)
  const segs: { start: number; text: string }[] = []
  for (let i = 0; i < tail.length; i += SEG) segs.push({ start: cut + i, text: tail.slice(i, i + SEG) })

  return (
    <div data-testid="streaming-text">
      {head && <Markdown text={head} />}
      {openFence ? (
        <div className="relative">
          <Markdown text={tail} />
          <span className="caret-ink" />
        </div>
      ) : (
        <p className="md-tail selectable whitespace-pre-wrap">
          {segs.map((s) => (
            <span key={s.start} className="ink-in">
              {s.text}
            </span>
          ))}
          <span className="caret-ink" />
        </p>
      )}
    </div>
  )
}
