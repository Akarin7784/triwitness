import clsx from 'clsx'
import { useEffect, useRef, useState } from 'react'
import { useReducedMotion } from '../hooks/useReducedMotion'
import { Markdown } from './Markdown'
import { closeOpenMarkdown, nextShown, settledBoundary } from '../lib/streamText'

const SEG = 6 // 尾段按 6 字一段淡入

/**
 * Claude 式流式正文：文字按帧平滑追上目标，新写出的片段轻轻淡入，结尾一个呼吸的软光标；
 * 已成段落的部分即时渲染为 Markdown（按块增量解析）。挂载时就已完成的消息（历史）直接整段显示，不播动画。
 */
export function StreamingText({ text, streaming }: { text: string; streaming: boolean }) {
  const reduced = useReducedMotion()
  const [animate] = useState(streaming) // 挂载时是否在写：决定播不播动画（之后不变）
  const [shown, setShown] = useState(() => (animate ? 0 : text.length))
  const target = reduced || !animate ? text.length : shown

  // 每帧最多一次提交：rAF 里推进，追上目标就停（不在 setState 的 updater 里排帧，StrictMode 下也只有一条链）
  const shownRef = useRef(shown)
  useEffect(() => {
    if (reduced || !animate) return
    let raf = 0
    const tick = () => {
      const n = nextShown(shownRef.current, text.length)
      shownRef.current = n
      setShown(n)
      if (n < text.length) raf = requestAnimationFrame(tick)
    }
    if (shownRef.current < text.length) raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [text, reduced, animate])

  const visible = text.slice(0, target)
  const writing = streaming || target < text.length

  // 写完后仍在同一位置渲染同一个 <Markdown>：已定稿的块（按起点 key + memo）原样保留，只补最后一块，
  // 不会在收尾时整篇重解析、整块替换 DOM。
  const cut = writing ? settledBoundary(visible) : text.length
  const head = writing ? visible.slice(0, cut) : text
  const tail = writing ? visible.slice(cut) : ''
  // 尾段里有 Markdown 标记（代码块 / 列表 / 行内代码 / 粗体）就按 Markdown 渲染；
  // 未闭合的反引号 / 粗体 / 代码围栏先临时补齐（走查 r2-1：不再露出「看起来 `fetch」这样的原始符号）
  const openFence = /```|`|\*\*|^\s*([-*]|\d+\.)\s|^#{1,3}\s/m.test(tail)
  const segs: { start: number; text: string }[] = []
  if (writing && !openFence) for (let i = 0; i < tail.length; i += SEG) segs.push({ start: cut + i, text: tail.slice(i, i + SEG) })

  // 光标：纯文本尾段直接跟在字后；Markdown 尾段 / 尾段为空时由 .stream-caret 伪元素贴在最后一段末尾，不单独占行
  return (
    <div data-testid={writing ? 'streaming-text' : undefined} className={clsx(writing && (openFence || !tail) && 'stream-caret')}>
      {head && <Markdown text={head} />}
      {writing && tail &&
        (openFence ? (
          <Markdown text={closeOpenMarkdown(tail)} />
        ) : (
          <p className="md-tail selectable whitespace-pre-wrap">
            {segs.map((s) => (
              <span key={s.start} className="ink-in">
                {s.text}
              </span>
            ))}
            <span className="caret-ink" />
          </p>
        ))}
      {writing && !head && !tail && <span className="caret-ink" />}
    </div>
  )
}

