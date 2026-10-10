// 验证：右键菜单、快捷键屏蔽、选区规则、剪贴板
import puppeteer from 'puppeteer-core'
const base = process.env.URL ?? 'http://localhost:1420'
const out = new URL('../docs/', import.meta.url).pathname
const browser = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox', '--hide-scrollbars'] })
await browser.defaultBrowserContext().overridePermissions(base, ['clipboard-read', 'clipboard-write', 'clipboard-sanitized-write'])
const page = await browser.newPage()
await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 })

const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const results = []
const check = (name, ok) => results.push(`${ok ? 'PASS' : 'FAIL'}  ${name}`)

await page.goto(base, { waitUntil: 'networkidle0' })
await page.evaluate(() => (window.__marker = 1))
await wait(1500)

// 1. 在 UI 空白处右键：不出菜单（找一个不在输入框 / 可选文本里的点，坐标不写死）
const blank = await page.evaluate(() => {
  const ok = (el) => el && !el.closest('textarea, input, [contenteditable="true"], .selectable, button, a')
  for (const [x, y] of [[720, 120], [1100, 200], [140, 600], [720, 60], [1300, 500]]) if (ok(document.elementFromPoint(x, y))) return [x, y]
  return null
})
check(`找到 UI 空白点 (${blank})`, !!blank)
await page.mouse.click(...(blank ?? [720, 60]), { button: 'right' })
await wait(250)
check('右键 UI 空白处无菜单', (await page.$('.ctx-menu')) === null)

// 2. 默认菜单被阻止（contextmenu 事件 defaultPrevented）
const prevented = await page.evaluate(() => {
  const ev = new MouseEvent('contextmenu', { bubbles: true, cancelable: true })
  document.body.dispatchEvent(ev)
  return ev.defaultPrevented
})
check('contextmenu 默认行为被 preventDefault', prevented)

// 3. 快捷键被拦截
for (const combo of [['F5'], ['Control', 'r'], ['Control', 'p'], ['Control', 'f'], ['Control', 'u'], ['F7'], ['Control', '='], ['Control', 'g']]) {
  const blocked = await page.evaluate((c) => {
    const key = c[c.length - 1]
    const ev = new KeyboardEvent('keydown', { key, ctrlKey: c.includes('Control'), bubbles: true, cancelable: true })
    document.body.dispatchEvent(ev)
    return ev.defaultPrevented
  }, combo)
  check(`拦截 ${combo.join('+')}`, blocked)
}
const ctrlWheel = await page.evaluate(() => {
  const ev = new WheelEvent('wheel', { deltaY: -100, ctrlKey: true, bubbles: true, cancelable: true })
  document.body.dispatchEvent(ev)
  return ev.defaultPrevented
})
check('拦截 Ctrl+滚轮缩放', ctrlWheel)
check('页面未被刷新', (await page.evaluate(() => window.__marker)) === 1)

// 4. 选区规则：UI 不可选，消息可选
const sel = await page.evaluate(() => ({
  sidebar: getComputedStyle(document.querySelector('aside nav [data-testid="chat-row"] span')).userSelect,
  message: getComputedStyle(document.querySelector('article .selectable')).userSelect,
  stream: getComputedStyle(document.querySelector('.selectable.font-mono') ?? document.body).userSelect,
}))
check(`侧栏不可选 (${sel.sidebar})`, sel.sidebar === 'none')
check(`消息可选 (${sel.message})`, sel.message === 'text')

// 5. 输入框里右键：自绘菜单
const ta = await page.$('textarea')
await ta.click()
await page.keyboard.type('修复 Issue #87 的并发刷新问题')
await page.evaluate(() => {
  const t = document.querySelector('textarea')
  t.setSelectionRange(0, t.value.length)
})
const box = await ta.boundingBox()
await page.mouse.click(box.x + 90, box.y + box.height / 2, { button: 'right' })
await wait(80)
// 右键会改变选区，重新设置后再打开一次
await page.evaluate(() => document.querySelector('textarea').setSelectionRange(0, document.querySelector('textarea').value.length))
await page.mouse.click(box.x + 90, box.y + box.height / 2, { button: 'right' })
await wait(400)
check('输入框右键出现自绘菜单', (await page.$('.ctx-menu')) !== null)
await page.hover('.ctx-item:nth-child(2)')
await wait(250)
{
  // 直接走 CDP 截图：不改视口，避免触发 resize 关闭菜单
  const fs = await import('node:fs')
  const cdp = await page.createCDPSession()
  const { data } = await cdp.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
  fs.writeFileSync(out + 'context-menu-full.png', Buffer.from(data, 'base64'))
  check('截图时菜单仍在', (await page.$('.ctx-menu')) !== null)
}
// 截图会触发 resize → 菜单按设计关闭；重新打开
await page.evaluate(() => window.dispatchEvent(new Event('resize')))
await wait(100)
check('改变窗口大小时菜单关闭', (await page.$('.ctx-menu')) === null)
await page.evaluate(() => document.querySelector('textarea').setSelectionRange(0, document.querySelector('textarea').value.length))
await page.mouse.click(box.x + 90, box.y + box.height / 2, { button: 'right' })
await wait(80)
await page.evaluate(() => document.querySelector('textarea').setSelectionRange(0, document.querySelector('textarea').value.length))
await page.mouse.click(box.x + 90, box.y + box.height / 2, { button: 'right' })
await wait(300)

// 6. 复制 → 粘贴
await page.click('.ctx-item:nth-child(2)')
await wait(200)
const clip = await page.evaluate(() => navigator.clipboard.readText())
check(`复制写入剪贴板 ("${clip}")`, clip.length > 0)
await page.evaluate(() => {
  const t = document.querySelector('textarea')
  t.focus()
  t.setSelectionRange(t.value.length, t.value.length)
})
await page.mouse.click(box.x + 300, box.y + box.height / 2, { button: 'right' })
await wait(300)
await page.click('.ctx-item:nth-child(3)')
await wait(300)
const val = await page.$eval('textarea', (t) => t.value)
check(`粘贴生效 ("${val}")`, val.endsWith(clip))

// 7. Esc 关闭
await page.mouse.click(box.x + 300, box.y + box.height / 2, { button: 'right' })
await wait(250)
await page.keyboard.press('Escape')
await wait(200)
check('Esc 关闭菜单', (await page.$('.ctx-menu')) === null)

// 8. 贴边：右下角附近打开不越界
await page.evaluate(() => {
  const t = document.querySelector('textarea')
  t.style.cssText += ';position:fixed;right:4px;bottom:4px;width:120px'
})
const b2 = await (await page.$('textarea')).boundingBox()
await page.mouse.click(b2.x + b2.width - 4, b2.y + b2.height - 4, { button: 'right' })
await wait(300)
const r = await page.$eval('.ctx-menu', (m) => m.getBoundingClientRect().toJSON())
check(`菜单在窗口内 (${Math.round(r.right)}≤1440, ${Math.round(r.bottom)}≤900)`, r.right <= 1440 && r.bottom <= 900 && r.left >= 0 && r.top >= 0)

console.log(results.join('\n'))
await browser.close()
