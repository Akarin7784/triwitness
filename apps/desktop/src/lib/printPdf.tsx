/**
 * 导出为 PDF：把 Markdown 渲染成一页干净的文档，放进隐藏 iframe，调系统打印（选“另存为 PDF”）。
 * 本机完成，不上传。
 */
import { renderToStaticMarkup } from 'react-dom/server'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const CSS = `
@page { margin: 18mm 16mm; }
body { font-family: "Noto Serif SC", "Source Han Serif SC", "Songti SC", serif; color: #2b2622; line-height: 1.8; font-size: 11pt; }
h1 { font-size: 20pt; font-weight: 600; margin: 0 0 4pt; }
h2 { font-size: 13pt; margin: 18pt 0 6pt; border-bottom: 0.5pt solid #d8cbb8; padding-bottom: 3pt; }
h3 { font-size: 11.5pt; margin: 12pt 0 4pt; }
em { color: #8a7a66; }
pre, code { font-family: "JetBrains Mono", Consolas, monospace; font-size: 9pt; }
pre { background: #f6f0e6; padding: 8pt; border-radius: 4pt; white-space: pre-wrap; word-break: break-all; }
blockquote { border-left: 2pt solid #c9a46c; margin: 0; padding-left: 8pt; color: #5b5149; }
details > summary { color: #8a7a66; }
table { border-collapse: collapse; } td, th { border: 0.5pt solid #d8cbb8; padding: 3pt 6pt; }
`

export function markdownToHtml(md: string, title: string): string {
  const body = renderToStaticMarkup(<ReactMarkdown remarkPlugins={[remarkGfm]}>{md}</ReactMarkdown>)
  const esc = title.replace(/[<>&]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' })[c]!)
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>${esc}</title><style>${CSS}</style></head><body>${body}</body></html>`
}

export function printMarkdown(md: string, title: string) {
  const frame = document.createElement('iframe')
  frame.setAttribute('aria-hidden', 'true')
  frame.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0;visibility:hidden'
  document.body.appendChild(frame)
  const doc = frame.contentDocument
  if (!doc) return
  doc.open()
  doc.write(markdownToHtml(md, title))
  doc.close()
  const go = () => {
    frame.contentWindow?.focus()
    frame.contentWindow?.print()
    window.setTimeout(() => frame.remove(), 60_000)
  }
  if (doc.readyState === 'complete') window.setTimeout(go, 50)
  else frame.onload = go
}
