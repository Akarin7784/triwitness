/** 右栏推流里整体不拆行的片段（走查 r2-3 / 批次 2-5） */
export const TOKEN_RE = /([^\s(（]+ ?[(（]\+\d+ [−-]\d+[)）]|\S+ → \d+ [A-Za-z]+|\$ write_file \S+)/

/**
 * 标准动效下最后两行逐字出现（走查 r1：token 被拆开）：按整行文本里的同一组 token 区间，
 * 把这些字包进不换行的 span；同时英文单词照常整体换行，写完变成整行文本时折行位置不变。
 */
export function tokenRanges(text: string): [number, number][] {
  const re = new RegExp(TOKEN_RE.source, 'g')
  const out: [number, number][] = []
  for (const m of text.matchAll(re)) out.push([m.index, m.index + m[0].length])
  return out
}
