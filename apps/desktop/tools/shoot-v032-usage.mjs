// v0.3.2：去掉预算控制后的 e2e（开发桥 + 打包核心 + 真实 key）：旧偏好迁移、发一句「你好」、用量页 / 状态栏只显示已花
// 用法：vite preview（TW_DEV_BRIDGE=1 TW_CORE=…）后  URL=http://localhost:1421 SHOTS=v0.3.2 node tools/shoot-v032-usage.mjs
// 出图：docs/images/v0.3.2/{usage-hello,usage-settings}.jpg
import puppeteer from 'puppeteer-core'
import { mkdirSync } from 'node:fs'
const base = process.env.URL ?? 'http://localhost:1420'
const out = new URL(`../../../docs/images/${process.env.SHOTS ?? 'v0.3.2'}/`, import.meta.url).pathname
mkdirSync(out, { recursive: true })
const browser = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox', '--hide-scrollbars'] })
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const results = []
const check = (name, ok) => (results.push(`${ok ? 'PASS' : 'FAIL'}  ${name}`), ok)
const page = await browser.newPage()
const errors = []
page.on('pageerror', (e) => errors.push(String(e)))
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1.5 })
const until = async (fn, ms = 60_000) => {
  const t0 = Date.now()
  while (Date.now() - t0 < ms) {
    if (await fn()) return true
    await wait(300)
  }
  return false
}
const text = (sel) => page.$eval(sel, (el) => el.textContent ?? '').catch(() => '')
const body = () => page.evaluate(() => document.body.innerText)

// 0.3.1 的旧偏好：单任务上限 ¥0.30 + 允许高峰 → 应被丢弃
await page.goto(`${base}/?source=new`, { waitUntil: 'networkidle0' })
await page.evaluate(() => {
  localStorage.clear()
  localStorage.setItem('tw.prefs', JSON.stringify({ permissionMode: 'auto_review', backend: 'none', maxCost: 0.3, allowPeak: true }))
})
await page.goto(`${base}/?source=new`, { waitUntil: 'networkidle0' })
check('状态栏显示已花（不是剩余）', await until(async () => /¥\d/.test(await text('[data-testid="status-spent"]')), 20_000))
const before = await text('[data-testid="status-spent"]')

await page.click('[data-testid="composer"] textarea')
await page.keyboard.type(`你好，这是 0.3.2 用量页验收（${new Date().toISOString().slice(11, 19)}）`, { delay: 5 })
await page.click('[data-testid="send"]')
check('回复结束', await until(async () => (await page.$$('[data-testid="message-actions"]')).length >= 1 && !(await page.$('[data-testid="stop"]')), 120_000))
const hello = await text('[data-testid="assistant-turn"]')
check(`回复：${hello.slice(0, 60)}`, hello.length > 0)
check('没有高峰 / 预算拦截提示', !/高峰时段被拒|允许高峰|超预算|预算上限/.test(await body()))
const saved = await page.evaluate(() => localStorage.getItem('tw.prefs') ?? '')
check('旧偏好 maxCost / allowPeak 已从存储里去掉', !saved.includes('maxCost') && !saved.includes('allowPeak'))
await page.mouse.move(1400, 880)
await wait(500)
await page.screenshot({ path: out + 'usage-hello.jpg', type: 'jpeg', quality: 86 })

// 旧链接 section=budget → 用量页（只读）
await page.goto(`${base}/?view=settings&section=budget`, { waitUntil: 'networkidle0' })
if (!(await page.$('[data-testid="usage-spent"]'))) {
  await page.goto(`${base}/?source=new`, { waitUntil: 'networkidle0' })
  await page.evaluate(() => document.querySelector('[data-testid="open-settings"]')?.click())
  await wait(500)
  await page.click('[data-testid="settings-nav-usage"]').catch(() => {})
}
check('用量页读到真实账本', await until(async () => /¥\d/.test(await text('[data-testid="usage-spent"]')), 20_000))
check('没有单任务上限滑块 / 高峰开关', !(await page.$('[data-testid="max-cost-row"]')) && !(await page.$('[data-testid="allow-peak"]')))
const b = await body()
check('用量页没有“剩余 / 总预算 / 熔断”', !/剩余|总预算|熔断|高峰闸门/.test(b))
check('按类别统计里有 chat', b.includes('chat'))
const after = await text('[data-testid="status-spent"]')
results.push(`INFO  状态栏 ${before} → ${after}；用量页 ${await text('[data-testid="usage-spent"]')} · ${await text('[data-testid="usage-calls"]')}`)
await page.mouse.move(1400, 880)
await wait(500)
await page.screenshot({ path: out + 'usage-settings.jpg', type: 'jpeg', quality: 86 })

check('无页面错误', errors.filter((e) => !/favicon|DevTools/.test(e)).length === 0)
console.log(results.join('\n'))
if (errors.length) console.log('errors:', errors.slice(0, 5).join('\n'))
await browser.close()
