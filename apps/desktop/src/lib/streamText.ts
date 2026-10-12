/** 流式正文的纯函数（UI-20），便于单测 */

/** 已稳定部分的边界：最后一个段落分隔（\n\n），且不在未闭合的代码块里 */
export function settledBoundary(text: string): number {
  let i = text.lastIndexOf('\n\n')
  while (i > 0) {
    const fences = (text.slice(0, i).match(/```/g) ?? []).length
    if (fences % 2 === 0) return i + 2
    i = text.lastIndexOf('\n\n', i - 1)
  }
  return 0
}

/** 每帧推进的字数：积压越多走得越快，平滑追上（约 150ms 内吃掉积压） */
export function nextShown(shown: number, target: number): number {
  if (shown >= target) return target
  return Math.min(target, shown + Math.max(1, Math.ceil((target - shown) * 0.12)))
}


/** 流式中途补齐未闭合的 Markdown 标记（只用于显示，不改原文） */
export function closeOpenMarkdown(md: string): string {
  let out = md
  const fences = (out.match(/^\s*```/gm) ?? []).length
  if (fences % 2) return out + '\n```'
  const inline = out.replace(/```[\s\S]*?```/g, '')
  if ((inline.match(/`/g) ?? []).length % 2) {
    // 刚敲下的反引号后还没有字：先藏起来，等内容到了再按代码显示
    out = /`$/.test(out) ? out.slice(0, -1) : out + '`'
  }
  const bold = (out.replace(/`[^`]*`/g, '').match(/\*\*/g) ?? []).length
  if (bold % 2) out = /\*\*$/.test(out) ? out.slice(0, -2) : out + '**'
  return out
}

/** 长路径中间省略：保留开头目录与文件名 */
export function middlePath(path: string, max = 30): string {
  if (path.length <= max) return path
  const keepTail = Math.ceil((max - 1) * 0.6)
  return path.slice(0, max - 1 - keepTail) + '…' + path.slice(path.length - keepTail)
}
