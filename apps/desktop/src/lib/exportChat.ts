/**
 * 导出 / 分享（UI-21 第 3 轮）：一轮对话 → Markdown。只在本机：不上传、不生成链接。
 * PDF 走系统打印（“另存为 PDF”），见 lib/printPdf.tsx。
 */
import type { ResultMsg } from '../bridge/protocol'
import type { Turn } from '../data/turns'
import type { ChatMessage } from '../types'
import { t } from './i18n'

export interface ExportInput {
  title: string
  turn: Turn | null
  messages: ChatMessage[]
  result: ResultMsg | null
  attachments?: string[]
  now?: Date
}

const VERDICT: Record<string, string> = { pass: t('复验通过'), fail: t('复验未过'), inconclusive: t('证据不足') }

function stamp(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

function quote(text: string): string {
  return text
    .split('\n')
    .map((l) => (l ? `> ${l}` : '>'))
    .join('\n')
}

export function chatToMarkdown({ title, turn, messages, result, attachments, now = new Date() }: ExportInput): string {
  const out: string[] = [`# ${title || t('三证会话')}`, '', t('_导出自 三证 · {0}（本机文件，未上传）_', stamp(now)), '']
  if (turn?.user) {
    out.push(t('## 你'), '', turn.user.text, '')
    if (attachments?.length) out.push(t('附件：{0}', attachments.map((a) => `\`${a}\``).join(t('、'))), '')
  }
  if (turn && (turn.blocks.length || turn.final)) {
    out.push(t('## 三证'), '')
    for (const b of turn.blocks) {
      if (b.type === 'thinking') out.push(t('<details><summary>思考</summary>'), '', b.text.trim(), '', '</details>', '')
      else if (b.type === 'text') out.push(b.text.trim(), '')
      else out.push(`- 🔧 \`${b.tool}\` ${b.display.replace(/^\$\s*/, '')}${b.ok ? '' : t('（失败）')}`, '')
    }
    if (turn.final) out.push(turn.final.text.trim(), '')
  }
  for (const m of messages) {
    out.push(`## ${m.role === 'user' ? t('你') : m.role === 'assistant' ? t('三证') : t('系统')}`, '', m.content.trim(), '')
  }
  if (result) {
    const head = [result.verdict ? VERDICT[result.verdict] : result.status, result.risk_level ? t('风险 {0}', result.risk_level) : null,
      `¥${result.cost_cny.toFixed(3)}`, t('{0} 步', result.steps)].filter(Boolean).join(' · ')  // prettier-ignore
    out.push(t('## 结论'), '', head, '')
    if (result.summary) out.push(quote(result.summary.trim()), '')
    if (result.branch) out.push(t('分支：`{0}`', result.branch), '')
    if (result.pr_md) out.push('### pr.md', '', result.pr_md.trim(), '')
  }
  return out.join('\n').replace(/\n{3,}/g, '\n\n').trimEnd() + '\n'
}

export function exportFileName(title: string, ext: string): string {
  const base = (title || t('三证会话')).replace(/[\\/:*?"<>|\r\n]+/g, ' ').trim().slice(0, 60) || t('三证会话')
  return `${base}.${ext}`
}
