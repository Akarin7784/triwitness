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

describe('设置页分段控件选中项对比度（b2b-r1 P1）', () => {
  const css = readFileSync(new URL('../index.css', import.meta.url), 'utf8')
  const pairs = [...css.matchAll(/--seg-on-fg: (#[0-9a-f]{6}); --seg-on-bg: (#[0-9a-f]{6});/g)].map((m) => [m[1], m[2]])
  it('日夜各一组且都 ≥ 4.5:1', () => {
    expect(pairs).toHaveLength(2)
    for (const [fg, bg] of pairs) expect(ratio(fg, bg)).toBeGreaterThanOrEqual(4.5)
  })
})
