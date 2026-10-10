/**
 * 作品（Artifacts，UI-21 第 3 轮）：从一轮对话里挑出值得放进侧栏的东西——
 * 较长的代码块、Markdown 文档（pr.md）、补丁（patch.diff）。同一会话的多个版本（重试 / 编辑）
 * 里同一作品按版本排列，侧栏可切换。纯函数，便于测试。
 */
import type { Turn } from '../data/turns'
import { t as tr } from './i18n'

export type ArtifactKind = 'code' | 'markdown' | 'diff'
export interface ArtifactVersion {
  /** 来自哪个会话版本（0 起） */
  from: number
  content: string
}
export interface Artifact {
  id: string
  title: string
  kind: ArtifactKind
  lang: string
  versions: ArtifactVersion[]
}
export interface VersionSource {
  turn: Turn | null
  prMd: string | null
  diff: string | null
}

const MIN_CODE_LINES = 6
const FENCE = /^(`{3,}|~{3,})([^\n`]*)\n([\s\S]*?)\n\1[ \t]*$/gm

const EXT: Record<string, string> = {
  python: 'py', py: 'py', typescript: 'ts', ts: 'ts', tsx: 'tsx', javascript: 'js', js: 'js', jsx: 'jsx', rust: 'rs',
  go: 'go', java: 'java', bash: 'sh', sh: 'sh', shell: 'sh', powershell: 'ps1', json: 'json', yaml: 'yaml', yml: 'yaml',
  toml: 'toml', html: 'html', css: 'css', sql: 'sql', markdown: 'md', md: 'md', diff: 'diff', c: 'c', cpp: 'cpp',
}

export function extOf(a: Pick<Artifact, 'kind' | 'lang'>): string {
  if (a.kind === 'diff') return 'diff'
  if (a.kind === 'markdown') return 'md'
  return EXT[a.lang.toLowerCase()] ?? 'txt'
}

export function fileNameOf(a: Pick<Artifact, 'kind' | 'lang' | 'title'>): string {
  if (/\.[a-z0-9]{1,6}$/i.test(a.title)) return a.title
  const base = a.title.replace(/[\\/:*?"<>|\s]+/g, '-').replace(/^-+|-+$/g, '') || 'artifact'
  return `${base}.${extOf(a)}`
}

/** 正文里的代码块（≥ 6 行）。标题取首行注释里的文件名，否则“代码 n · 语言” */
export function codeBlocks(text: string): { lang: string; code: string; title: string | null }[] {
  const out: { lang: string; code: string; title: string | null }[] = []
  for (const m of text.matchAll(FENCE)) {
    const info = m[2].trim()
    const code = m[3]
    if (code.split('\n').length < MIN_CODE_LINES) continue
    const lang = info.split(/\s+/)[0] ?? ''
    const named = /^\s*(?:#|\/\/|--|<!--)\s*([\w./-]+\.[a-z0-9]{1,6})\b/i.exec(code.split('\n')[0])
    out.push({ lang: lang === 'diff' ? 'diff' : lang, code, title: named?.[1] ?? (info.includes('.') ? (info.split(/\s+/).pop() ?? null) : null) })
  }
  return out
}

function turnText(t: Turn): string {
  return [...t.blocks.flatMap((b) => (b.type === 'text' ? [b.text] : [])), t.final?.text ?? ''].join('\n\n')
}

/** 把各版本的来源合成作品清单；versions 按会话版本顺序，内容没变的版本不重复记 */
export function collectArtifacts(sources: VersionSource[]): Artifact[] {
  const map = new Map<string, Artifact>()
  const add = (id: string, title: string, kind: ArtifactKind, lang: string, from: number, content: string) => {
    if (!content.trim()) return
    let a = map.get(id)
    if (!a) {
      a = { id, title, kind, lang, versions: [] }
      map.set(id, a)
    }
    const last = a.versions[a.versions.length - 1]
    if (last?.content === content) return
    a.versions.push({ from, content })
  }
  sources.forEach((s, from) => {
    if (s.turn) {
      codeBlocks(turnText(s.turn)).forEach((c, i) => {
        const kind: ArtifactKind = c.lang === 'diff' ? 'diff' : c.lang === 'markdown' || c.lang === 'md' ? 'markdown' : 'code'
        const id = c.title ? `file:${c.title}` : `code:${i}`
        add(id, c.title ?? tr('代码 {0}{1}', i + 1, c.lang ? ` · ${c.lang}` : ''), kind, c.lang, from, c.code)
      })
    }
    if (s.diff) add('patch.diff', 'patch.diff', 'diff', 'diff', from, s.diff)
    if (s.prMd) add('pr.md', 'pr.md', 'markdown', 'markdown', from, s.prMd)
  })
  return [...map.values()]
}

export type DiffLineKind = 'add' | 'del' | 'hunk' | 'meta' | 'ctx'
export function diffLineKind(line: string): DiffLineKind {
  if (line.startsWith('+++') || line.startsWith('---') || line.startsWith('diff ') || line.startsWith('index ')) return 'meta'
  if (line.startsWith('@@')) return 'hunk'
  if (line.startsWith('+')) return 'add'
  if (line.startsWith('-')) return 'del'
  return 'ctx'
}

export function diffStats(diff: string): { files: number; add: number; del: number } {
  let files = 0
  let add = 0
  let del = 0
  for (const l of diff.split('\n')) {
    if (l.startsWith('diff --git')) files++
    else if (l.startsWith('+') && !l.startsWith('+++')) add++
    else if (l.startsWith('-') && !l.startsWith('---')) del++
  }
  return { files, add, del }
}
