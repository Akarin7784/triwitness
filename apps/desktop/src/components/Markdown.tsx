import { memo, useState, type ReactNode } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Check, Copy } from 'lucide-react'

function textOf(node: ReactNode): string {
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(textOf).join('')
  if (node && typeof node === 'object' && 'props' in node) {
    return textOf((node as { props: { children?: ReactNode } }).props.children)
  }
  return ''
}

export function CopyButton({ text, label = '复制', className }: { text: string; label?: string; className?: string }) {
  const [done, setDone] = useState(false)
  return (
    <button
      type="button"
      aria-label={label}
      onClick={() => {
        void navigator.clipboard?.writeText(text).then(() => {
          setDone(true)
          window.setTimeout(() => setDone(false), 1400)
        })
      }}
      className={
        className ??
        'inline-flex h-6 items-center gap-1 rounded-md px-1.5 text-[11px] text-sepia-muted transition-colors duration-300 hover:bg-panel-raised hover:text-amber'
      }
    >
      {done ? <Check size={12} strokeWidth={1.8} /> : <Copy size={12} strokeWidth={1.6} />}
      {done ? '已复制' : null}
    </button>
  )
}

function CodeBlock({ children }: { children?: ReactNode }) {
  const child = Array.isArray(children) ? children[0] : children
  const cls = (child as { props?: { className?: string } } | undefined)?.props?.className ?? ''
  const lang = /language-([\w+-]+)/.exec(cls)?.[1] ?? ''
  const code = textOf(child).replace(/\n$/, '')
  return (
    <div className="md-code group/code my-3 overflow-hidden rounded-xl border border-border-soft">
      <div className="flex h-7 items-center justify-between bg-parchment-deep/60 pl-3 pr-1">
        <span className="font-mono text-[10.5px] tracking-wide text-sepia-muted">{lang}</span>
        <CopyButton text={code} label="复制代码" />
      </div>
      <pre className="selectable overflow-x-auto scroll-soft bg-cream/80 px-3.5 py-2.5 font-mono text-[12.5px] leading-relaxed text-ink">
        <code>{code}</code>
      </pre>
    </div>
  )
}

const COMPONENTS: Components = {
  pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
  code: ({ children, className }) =>
    className ? (
      <code className={className}>{children}</code>
    ) : (
      <code className="rounded bg-parchment-deep/70 px-1 py-px font-mono text-[0.88em] text-espresso">{children}</code>
    ),
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer" className="text-amber underline decoration-amber/40 underline-offset-2">
      {children}
    </a>
  ),
}

/** 助手正文的 Markdown：段落 / 列表 / 行内代码 / 代码块（带复制）/ 表格；不渲染原始 HTML */
export const Markdown = memo(function Markdown({ text }: { text: string }) {
  return (
    <div className="md selectable">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={COMPONENTS}>
        {text}
      </ReactMarkdown>
    </div>
  )
})
