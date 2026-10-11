import { lazy, memo, Suspense, useMemo } from 'react'
import { splitMdBlocks } from '../lib/mdBlocks'
import { loadMarkdownRenderer } from '../lib/markdownLoader'

export { CopyButton } from './CopyButton'

const MarkdownChunk = lazy(loadMarkdownRenderer)

/**
 * 助手正文的 Markdown：段落 / 列表 / 行内代码 / 代码块（带复制）/ 表格；不渲染原始 HTML。
 * 增量：按顶层块切开、每块 memo（key = 块起点），文本只在尾部增长时只有最后一块重解析。
 * 渲染器 chunk 还没到时先显示同版式的纯文本（一般只在冷启动的头一帧）。
 */
export const Markdown = memo(function Markdown({ text }: { text: string }) {
  const blocks = useMemo(() => splitMdBlocks(text), [text])
  return (
    <div className="md selectable">
      <Suspense fallback={<p className="whitespace-pre-wrap">{text}</p>}>
        {blocks.map((b) => (
          <MarkdownChunk key={b.start} text={b.text} />
        ))}
      </Suspense>
    </div>
  )
})
