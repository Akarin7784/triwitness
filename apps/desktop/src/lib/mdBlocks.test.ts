import { describe, expect, it } from 'vitest'
import { splitMdBlocks } from './mdBlocks'

const texts = (s: string) => splitMdBlocks(s).map((b) => b.text)

describe('splitMdBlocks', () => {
  it('按空行切顶层块，拼回来等于原文', () => {
    const s = '第一段\n\n- a\n- b\n\n第三段'
    expect(texts(s)).toEqual(['第一段\n\n', '- a\n- b\n\n', '第三段'])
    expect(texts(s).join('')).toBe(s)
    expect(splitMdBlocks(s).map((b) => b.start)).toEqual([0, 5, 14])
  })
  it('代码围栏里的空行不切', () => {
    const s = '前\n\n```py\na = 1\n\nb = 2\n```\n\n后'
    expect(texts(s)).toEqual(['前\n\n', '```py\na = 1\n\nb = 2\n```\n\n', '后'])
  })
  it('未闭合围栏（流式中）整段归一块', () => {
    expect(texts('段\n\n```\nx\n\ny')).toEqual(['段\n\n', '```\nx\n\ny'])
  })
  it('缩进续行并入上一块（列表项的第二段 / 缩进代码）', () => {
    const s = '- 项\n\n  续一段\n\n下一段'
    expect(texts(s)).toEqual(['- 项\n\n  续一段\n\n', '下一段'])
  })
  it('有引用式定义时整篇不切', () => {
    const s = '见 [文档][d]\n\n[d]: https://example.com'
    expect(texts(s)).toEqual([s])
  })
  it('空串 / 无空行', () => {
    expect(splitMdBlocks('')).toEqual([])
    expect(texts('一行')).toEqual(['一行'])
  })
  it('前面的块在追加后保持不变（memo 命中）', () => {
    const a = splitMdBlocks('甲\n\n乙\n\n')
    const b = splitMdBlocks('甲\n\n乙\n\n丙丙')
    expect(b.slice(0, 2)).toEqual(a)
  })
})
