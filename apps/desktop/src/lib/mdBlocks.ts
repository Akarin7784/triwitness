/**
 * 增量 Markdown（perf）：把正文切成顶层块（空行分隔、不在代码围栏里），每块单独解析并按内容 memo。
 * 流式写作时只有最后一块在变，前面的块不再重复解析（原来每定稿一段就把整段 head 重解析一遍，O(n²)）。
 * 保守切分：缩进开头的段（列表项续行 / 缩进代码）并入上一块；出现引用式定义（[x]: url、[^1]:）时整篇不切。
 */
export interface MdBlock {
  start: number
  text: string
}

const FENCE = /^ {0,3}(```|~~~)/
const DEFINITION = /^ {0,3}\[[^\]\n]+\]:\s/m

export function splitMdBlocks(text: string): MdBlock[] {
  if (!text) return []
  if (DEFINITION.test(text)) return [{ start: 0, text }]
  const out: MdBlock[] = []
  let fence: string | null = null
  let blockStart = 0
  let afterBlank = false
  let pos = 0
  for (;;) {
    const nl = text.indexOf('\n', pos)
    const line = text.slice(pos, nl === -1 ? text.length : nl)
    if (fence) {
      if (FENCE.exec(line)?.[1] === fence) fence = null
    } else if (line.trim() === '') {
      afterBlank = true
    } else {
      // 空行之后、顶格开始的一行 → 新块
      if (afterBlank && pos > blockStart && !/^\s/.test(line)) {
        out.push({ start: blockStart, text: text.slice(blockStart, pos) })
        blockStart = pos
      }
      afterBlank = false
      fence = FENCE.exec(line)?.[1] ?? null
    }
    if (nl === -1) break
    pos = nl + 1
  }
  if (blockStart < text.length) out.push({ start: blockStart, text: text.slice(blockStart) })
  return out
}
