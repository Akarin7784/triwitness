/**
 * 代码块语法高亮（批次 1 合并前补）：highlight.js core + 少量常用语言，本地打包、随 Markdown 懒加载 chunk 走。
 * 未闭合的流式代码块同样可高亮（hljs 逐 token 容错，不要求完整语法）。输出已转义，可直接作 innerHTML。
 */
import hljs from 'highlight.js/lib/core'
import python from 'highlight.js/lib/languages/python'
import typescript from 'highlight.js/lib/languages/typescript'
import javascript from 'highlight.js/lib/languages/javascript'
import bash from 'highlight.js/lib/languages/bash'
import json from 'highlight.js/lib/languages/json'
import diff from 'highlight.js/lib/languages/diff'
import yaml from 'highlight.js/lib/languages/yaml'
import ini from 'highlight.js/lib/languages/ini'
import rust from 'highlight.js/lib/languages/rust'
import xml from 'highlight.js/lib/languages/xml'
import css from 'highlight.js/lib/languages/css'

const LANGS = { python, typescript, javascript, bash, json, diff, yaml, ini, rust, xml, css }
for (const [name, def] of Object.entries(LANGS)) hljs.registerLanguage(name, def)
hljs.registerAliases(['py'], { languageName: 'python' })
hljs.registerAliases(['ts', 'tsx'], { languageName: 'typescript' })
hljs.registerAliases(['js', 'jsx', 'mjs'], { languageName: 'javascript' })
hljs.registerAliases(['sh', 'shell', 'console', 'zsh'], { languageName: 'bash' })
hljs.registerAliases(['toml'], { languageName: 'ini' })
hljs.registerAliases(['rs'], { languageName: 'rust' })
hljs.registerAliases(['html', 'svg'], { languageName: 'xml' })
hljs.registerAliases(['patch'], { languageName: 'diff' })

/** 返回高亮后的 HTML；未知语言 / 无语言返回 null（按纯文本显示，不做自动猜测，避免误着色） */
export function highlightCode(code: string, lang: string): string | null {
  if (!lang || !hljs.getLanguage(lang)) return null
  try {
    return hljs.highlight(code, { language: lang, ignoreIllegals: true }).value
  } catch {
    return null
  }
}
