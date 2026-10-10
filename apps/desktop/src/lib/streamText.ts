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

