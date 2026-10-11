// v0.3.2：断点续跑 e2e（真实 key）——起一个小任务，写下第一个文件后点停止，再点「继续」，等结论卡
// 用法：TW_DEV_BRIDGE=1 TW_CORE='["<onedir>/tw"]' vite preview 后  URL=… REPO=<verses> node tools/shoot-v032-resume.mjs
import puppeteer from 'puppeteer-core'
import { mkdirSync } from 'node:fs'
const base = process.env.URL ?? 'http://localhost:1421'
const out = new URL(`../../../docs/images/${process.env.SHOTS ?? 'v0.3.2'}/`, import.meta.url).pathname
mkdirSync(out, { recursive: true })
const REPO = process.env.REPO ?? ''
const TASK = process.env.TASK ?? 'line_count 把空行也算进去了：「床前明月光\\n\\n疑是地上霜\\n」应为 2 行，实际返回 4。帮我修一下。'
const EXTRA = { permissionMode: process.env.MODE ?? 'auto_review', backend: process.env.BACKEND ?? 'none' }
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
const calm = async () => {
  await page.mouse.move(1400, 880)
  await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur())
}
const approveAll = () =>
  page.evaluate(() => [...document.querySelectorAll('[data-testid="approval-card"] button')].find((b) => b.textContent === '允许一次')?.click())

await page.goto(`${base}/?source=new`, { waitUntil: 'networkidle0' })
await page.evaluate((extra, repo) => {
  localStorage.clear()
  localStorage.setItem('tw.prefs', JSON.stringify(extra))
  localStorage.setItem('tw.core.repo', repo)
}, EXTRA, REPO)
await page.goto(`${base}/?source=new`, { waitUntil: 'networkidle0' })
await page.click('[data-testid="composer"] textarea')
await page.keyboard.type(TASK, { delay: 5 })
await page.click('[data-testid="send"]')

// 1) 第一个写文件动作出现后停止
const wrote = await until(async () => {
  await approveAll()
  return page.evaluate(() => /write_file|edit_file/.test(document.body.innerText))
}, 300_000)
check('出现写文件动作', wrote)
await wait(4000) // 让这一步收尾、核心落盘进度
await approveAll()
await page.click('[data-testid="stop"]').catch(() => {})
check('已停止', await until(async () => !(await page.$('[data-testid="stop"]')), 30_000))
check('出现「继续」', await until(async () => !!(await page.$('[data-testid="continue"]')), 30_000))
await calm()
await wait(600)
await page.screenshot({ path: out + 'resume-stopped.jpg', type: 'jpeg', quality: 86 })

// 2) 继续 → 结论卡
const cardsBefore = (await page.$$('[data-testid="result-card"]')).length
await page.click('[data-testid="continue"]')
const done = await until(async () => {
  await approveAll()
  return (await page.$$('[data-testid="result-card"]')).length > cardsBefore && !(await page.$('[data-testid="stop"]'))
}, 600_000)
check('续跑出结论卡', done)
await wait(2000)
const card = await page.$$eval('[data-testid="result-card"]', (els) => els.at(-1)?.textContent ?? '').catch(() => '')
check(`结论：${card.replace(/\s+/g, ' ').slice(0, 100)}`, card.length > 0)
const body = await page.evaluate(() => document.body.innerText)
check('续跑结论是复验通过', card.includes('复验通过'))
check('续跑轮显示「继续」', body.includes('继续'))
const cost = await page.$$eval('[data-testid="result-cost"]', (els) => `${els.at(-1)?.textContent} | ${els.at(-1)?.getAttribute('title')}`).catch(() => '')
console.log(`COST ${cost}`)
await page.evaluate(() => [...document.querySelectorAll('[data-testid="result-card"]')].at(-1)?.scrollIntoView({ block: 'end' }))
await calm()
await wait(500)
await page.screenshot({ path: out + 'resume-done.jpg', type: 'jpeg', quality: 86 })
check(`没有页面错误（${errors.length}）`, errors.length === 0)
if (errors.length) console.log(errors.slice(0, 5).join('\n'))
console.log(results.join('\n'))
await browser.close()
process.exit(results.some((r) => r.startsWith('FAIL')) ? 1 : 0)
