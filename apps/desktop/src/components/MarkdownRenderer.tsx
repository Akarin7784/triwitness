/**
 * Markdown 渲染器（懒加载 chunk：react-markdown + remark-gfm 不进主包）。
 * 一次只解析一个顶层块（见 lib/mdBlocks），按内容 memo——已定稿的块不再重复解析。
 */
import { memo, type ReactNode } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { PanelRight } from 'lucide-react'
import { CopyButton } from './CopyButton'
import { t } from '../lib/i18n'

function textOf(node: ReactNode): string {
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(textOf).join('')
  if (node && typeof node === 'object' && 'props' in node) {
    return textOf((node as { props: { children?: ReactNode } }).props.children)
  }
  return ''
}

function CodeBlock({ children }: { children?: ReactNode }) {
  const child = Array.isArray(children) ? children[0] : children
  const cls = (child as { props?: { className?: string } } | undefined)?.props?.className ?? ''
  const lang = /language-([\w+-]+)/.exec(cls)?.[1] ?? ''
  const code = textOf(child).replace(/\n$/, '')
  return (
    <div className="md-code group/code my-3 overflow-hidden rounded-xl border border-border-soft">
      <div className="flex h-7 items-center justify-between bg-parchment-deep/60 pl-3 pr-1">
        <span className="font-mono text-[13px] tracking-wide text-sepia-muted">{lang}</span>
        <span className="flex items-center">
          {code.split('\n').length >= 6 && (
            <button
              type="button"
              aria-label={t('在作品栏打开')}
              data-testid="code-open-artifact"
              onClick={() => window.dispatchEvent(new CustomEvent('tw:open-artifact', { detail: code }))}
              className="inline-flex h-6 items-center rounded-md px-1.5 text-sepia-muted transition-colors duration-300 hover:bg-panel-raised hover:text-amber-ink"
            >
              <PanelRight size={12} strokeWidth={1.6} />
            </button>
          )}
          <CopyButton text={code} label={t('复制代码')} />
        </span>
      </div>
      <pre className="selectable overflow-x-auto scroll-soft bg-cream/80 px-3.5 py-2.5 font-mono text-[13px] leading-relaxed text-ink">
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
    <a href={href} target="_blank" rel="noreferrer" className="text-amber-ink underline decoration-amber/40 underline-offset-2">
      {children}
    </a>
  ),
}

const PLUGINS = [remarkGfm]

/** 一个顶层块；react-markdown 10 不包外层元素，块直接落进 .md 容器，DOM 与整篇解析一致 */
const MarkdownChunk = memo(function MarkdownChunk({ text }: { text: string }) {
  return (
    <ReactMarkdown remarkPlugins={PLUGINS} components={COMPONENTS}>
      {text}
    </ReactMarkdown>
  )
})

export default MarkdownChunk
