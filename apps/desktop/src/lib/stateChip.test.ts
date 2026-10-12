import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const lum = (hex: string) => {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
}
const ratio = (a: string, b: string) => {
  const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m)
  return (x + 0.05) / (y + 0.05)
}

describe('会话状态签（阿验 b2 合并后 P2）', () => {
  const css = readFileSync(new URL('../index.css', import.meta.url), 'utf8')
  const light = (name: string) => new RegExp(`--color-${name}: (#[0-9a-f]{6});`).exec(css)![1]
  it('日间「完成」字色对页面底和胶囊底都 ≥ 7:1', () => {
    const fg = /--state-done-fg: (#[0-9a-f]{6});/.exec(css)![1]
    for (const bg of [light('parchment'), light('cream'), light('parchment-deep')]) expect(ratio(fg, bg)).toBeGreaterThanOrEqual(7)
  })
  it('夜间「完成」保持原来的 sepia', () => {
    expect(css).toMatch(/:root\[data-theme='dark'\] \.state-chip\[data-phase='done'\] \{ color: var\(--color-sepia\); \}/)
  })
  it('有固定最小宽度（按「进行中」三个字 + 点 + 间距 + 内边距）', () => {
    expect(css).toMatch(/\.state-chip \{ min-width: calc\(7px \+ 6px \+ 3em \+ 22px\); justify-content: center; \}/)
  })
})
