// 共用的页面内检查（shoot-review / shoot-feedback）。函数要自包含：会被序列化进浏览器执行。
// ── 标签换行（在浏览器里跑）：按钮 / chip / 菜单项 / 单选 / 标签页里任何一段文字折成两行，或 nowrap 溢出未省略
//   允许换行的说明文字标 data-allow-wrap
export function wrapInPage() {
  const vis = (el) => {
    const r = el.getBoundingClientRect()
    if (r.width < 1 || r.height < 1) return false
    for (let e = el; e; e = e.parentElement) {
      const cs = getComputedStyle(e)
      if (cs.visibility === 'hidden' || cs.display === 'none' || Number(cs.opacity) < 0.05) return false
    }
    return true
  }
  const bad = []
  const sel = 'button, [role="menuitem"], [role="menuitemradio"], [role="radio"], [role="tab"], .chip, .menu-item'
  for (const el of document.querySelectorAll(sel)) {
    if (!vis(el) || el.closest('[data-allow-wrap]') || el.closest('.md, article, [data-testid="composer"] textarea')) continue
    const text = (el.innerText ?? '').trim()
    if (!text) continue
    const leaves = [...el.querySelectorAll('*'), el].filter((s) => [...s.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()))
    for (const t of leaves) {
      if (t.closest('[data-allow-wrap]')) continue
      const cs = getComputedStyle(t)
      if (cs.display === 'block' && t.tagName === 'P') continue
      const range = document.createRange()
      range.selectNodeContents(t)
      // 同一行里混排字体（¥ / 中文 / 拉丁）会给出 top 差 1–2px 的多个矩形：按半个行高聚类再数行
      const rects = [...range.getClientRects()].filter((r) => r.width > 0.5).sort((a, b) => a.top - b.top)
      let lines = rects.length ? 1 : 0
      for (let i = 1; i < rects.length; i++) if (rects[i].top - rects[i - 1].top > Math.min(rects[i].height, rects[i - 1].height) * 0.6) lines++
      if (lines > 1 && !/^(nowrap|pre)$/.test(cs.whiteSpace)) {
        bad.push(`wrap ${el.getAttribute('data-testid') ?? el.tagName.toLowerCase()}「${text.replace(/\s+/g, ' ').slice(0, 24)}」`)
        break
      }
      if (cs.whiteSpace === 'nowrap' && cs.overflowX === 'visible' && cs.display !== 'inline' && t.scrollWidth > t.clientWidth + 1) {
        bad.push(`overflow ${el.getAttribute('data-testid') ?? el.tagName.toLowerCase()}「${text.replace(/\s+/g, ' ').slice(0, 24)}」`)
        break
      }
    }
  }
  return [...new Set(bad)]
}
