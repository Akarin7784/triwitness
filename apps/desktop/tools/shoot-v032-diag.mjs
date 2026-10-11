// v0.3.2：诊断包 e2e（开发桥 + 打包核心 + 真实 key）——发一句话 → 关于页「导出诊断包」→ 提示 zip 路径
// 用法：vite preview（TW_DEV_BRIDGE=1 TW_CORE=…）后  URL=… node tools/shoot-v032-diag.mjs   出图：docs/images/v0.3.2/diag-export.jpg
import puppeteer from 'puppeteer-core'
import { mkdirSync } from 'node:fs'
const base = process.env.URL ?? 'http://localhost:1421'
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
const body = () => page.evaluate(() => document.body.innerText)
await page.goto(`${base}/?source=new`, { waitUntil: 'networkidle0' })
await page.evaluate(() => {
  localStorage.clear()
  localStorage.setItem('tw.prefs', JSON.stringify({ permissionMode: 'auto_review', backend: 'none' }))
})
await page.goto(`${base}/?source=new`, { waitUntil: 'networkidle0' })
await page.click('[data-testid="composer"] textarea')
await page.keyboard.type(`一句话回答：诊断包里应该放什么？（0.3.2 验收 ${new Date().toISOString().slice(11, 19)}）`, { delay: 5 })
await page.click('[data-testid="send"]')
check('回复结束', await until(async () => (await page.$$('[data-testid="message-actions"]')).length >= 1 && !(await page.$('[data-testid="stop"]')), 120_000))
await page.goto(`${base}/?view=settings&section=about`, { waitUntil: 'networkidle0' })
if (!(await page.$('[data-testid="export-diag"]'))) {
  await page.evaluate(() => document.querySelector('[data-testid="open-settings"]')?.click())
  await wait(500)
  await page.click('[data-testid="settings-nav-about"]').catch(() => {})
}
check('关于页有「导出诊断包」', await until(async () => !!(await page.$('[data-testid="export-diag"]')), 10_000))
await page.click('[data-testid="export-diag"]')
const ok = await until(async () => /诊断包已导出|导出诊断包失败/.test(await body()), 60_000)
const msg = (await body()).match(/诊断包已导出[^\n]*|导出诊断包失败[^\n]*/)?.[0] ?? ''
check(`提示：${msg}`, ok && msg.startsWith('诊断包已导出'))
console.log(`DIAG_PATH ${msg.split('：').at(-1)}`)
await page.mouse.move(1400, 880)
await wait(400)
await page.screenshot({ path: out + 'diag-export.jpg', type: 'jpeg', quality: 86 })
check('无页面错误', errors.filter((e) => !/favicon|DevTools/.test(e)).length === 0)
console.log(results.join('\n'))
if (errors.length) console.log('errors:', errors.slice(0, 5).join('\n'))
await browser.close()
