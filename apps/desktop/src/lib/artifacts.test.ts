import { describe, expect, it } from 'vitest'
import { codeBlocks, collectArtifacts, diffLineKind, diffStats, fileNameOf } from './artifacts'
import { chatToMarkdown, exportFileName } from './exportChat'
import { EMPTY_TURN, type Turn } from '../data/turns'

const long = (n: number) => Array.from({ length: n }, (_, i) => `line${i}`).join('\n')
const turnWith = (text: string): Turn => ({
  ...EMPTY_TURN,
  user: { text: '修 bug', time: '10:00', repo: 'r' },
  blocks: [{ type: 'text', id: 't', callId: 'c', text, done: true }],
})

describe('artifacts', () => {
  it('只收 ≥6 行的代码块，首行注释里的文件名作标题', () => {
    const text = `看这里\n\n\`\`\`python\n# rows.py\n${long(6)}\n\`\`\`\n\n\`\`\`sh\nls\n\`\`\``
    const c = codeBlocks(text)
    expect(c).toHaveLength(1)
    expect(c[0]).toMatchObject({ lang: 'python', title: 'rows.py' })
  })
  it('跨版本合并，内容没变不重复', () => {
    const v1 = { turn: turnWith(`\`\`\`ts\n${long(7)}\n\`\`\``), prMd: '# PR\n一', diff: 'diff --git a/x b/x\n+1\n-2' }
    const v2 = { turn: turnWith(`\`\`\`ts\n${long(8)}\n\`\`\``), prMd: '# PR\n一', diff: null }
    const arts = collectArtifacts([v1, v2])
    expect(arts.map((a) => [a.id, a.versions.map((v) => v.from)])).toEqual([
      ['code:0', [0, 1]],
      ['patch.diff', [0]],
      ['pr.md', [0]],
    ])
    expect(fileNameOf(arts[0])).toBe('代码-1-·-ts.ts')
    expect(fileNameOf(arts[2])).toBe('pr.md')
  })
  it('diff 行与统计', () => {
    expect(['+++ b', '@@ -1 +1 @@', '+a', '-b', ' c'].map(diffLineKind)).toEqual(['meta', 'hunk', 'add', 'del', 'ctx'])
    expect(diffStats('diff --git a b\n--- a\n+++ b\n+x\n+y\n-z')).toEqual({ files: 1, add: 2, del: 1 })
  })
})

describe('export', () => {
  it('Markdown 含标题、你、三证、结论；说明是本机文件', () => {
    const md = chatToMarkdown({
      title: '修复空行',
      turn: { ...turnWith('改好了'), final: { text: '完成', meta: '', time: '', status: 'done' } },
      messages: [],
      result: { bridge: 'result', status: 'done', run_dir: '/r', branch: 'tw/1', backend: 'none', cost_cny: 0.0123, steps: 4,
        reason: null, summary: '跳过空行', verdict: 'pass', risk_level: 'L1', clean_env: 'verified', pr_md: '# PR' },  // prettier-ignore
      attachments: ['a.md'],
      now: new Date(2026, 9, 11, 9, 5),
    })
    expect(md).toContain('# 修复空行')
    expect(md).toContain('_导出自 三证 · 2026-10-11 09:05（本机文件，未上传）_')
    expect(md).toContain('## 你\n\n修 bug\n\n附件：`a.md`')
    expect(md).toContain('复验通过 · 风险 L1 · ¥0.012 · 4 步')
    expect(md).toContain('> 跳过空行')
    expect(md.endsWith('# PR\n')).toBe(true)
  })
  it('文件名清洗', () => {
    expect(exportFileName('a/b:c?', 'md')).toBe('a b c.md')
    expect(exportFileName('', 'pdf')).toBe('三证会话.pdf')
  })
})
