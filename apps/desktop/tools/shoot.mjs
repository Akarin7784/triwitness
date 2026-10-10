// 实时截图（rAF 驱动的动画在 headless 虚拟时间下不走，所以用真实等待）
import puppeteer from 'puppeteer-core'
const base = process.env.URL ?? 'http://localhost:1420'
const out = new URL('../docs/', import.meta.url).pathname
const browser = await puppeteer.launch({
  executablePath: '/usr/bin/google-chrome',
  headless: true,
  args: ['--no-sandbox', '--hide-scrollbars'],
})
const page = await browser.newPage()
await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 })
const wait = (ms) => new Promise((r) => setTimeout(r, ms))

await page.goto(base, { waitUntil: 'networkidle0' })
await wait(11000)
await page.screenshot({ path: out + 'main-midstream.png' })
// 特写：右侧推流面板
const panel = await page.$('aside:last-of-type')
if (panel) await panel.screenshot({ path: out + 'stream-closeup.png' })
await wait(26000)
await page.screenshot({ path: out + 'main-stream-late.png' })

await page.goto(base + '/?view=settings', { waitUntil: 'networkidle0' })
await wait(1200)
await page.screenshot({ path: out + 'settings.png' })
await page.setViewport({ width: 1440, height: 1700, deviceScaleFactor: 1.5 })
await wait(600)
await page.screenshot({ path: out + 'settings-full.png' })

// 标题栏特写 + 悬停提示示例
await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 })
await page.goto(base, { waitUntil: 'networkidle0' })
await wait(4000)
await page.hover('.win-btn-close')
await wait(500)
await page.screenshot({ path: out + 'titlebar.png', clip: { x: 0, y: 0, width: 1440, height: 120 } })
await page.hover('footer .sb-item')
await wait(900)
await page.screenshot({ path: out + 'tooltip.png', clip: { x: 0, y: 780, width: 520, height: 120 } })

// 减少动态效果
await page.emulateMediaFeatures([{ name: 'prefers-reduced-motion', value: 'reduce' }])
await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 })
await page.goto(base, { waitUntil: 'networkidle0' })
await wait(5000)
await page.screenshot({ path: out + 'main-reduced-motion.png' })

// 离线字体检查：确认没有请求外部域名
const ext = []
page.on('request', (r) => { if (!r.url().startsWith(base)) ext.push(r.url()) })
await page.reload({ waitUntil: 'networkidle0' })
const fonts = await page.evaluate(async () => {
  await document.fonts.ready
  return [...document.fonts].filter((f) => f.status === 'loaded').map((f) => f.family + ' ' + f.weight)
})
console.log('external requests:', ext.length, ext.slice(0, 3))
console.log('loaded font faces:', [...new Set(fonts)].join(', '))
await browser.close()
