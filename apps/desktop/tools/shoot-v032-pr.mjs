// v0.3.2：开 PR e2e（真实 key + 真实 GitHub 临时仓库）——小任务 → 结论卡「开 PR」→ 审批卡（仓库/分支/标题）→ 确认 → PR 链接
// 用法：vite preview（TW_DEV_BRIDGE=1 TW_CORE=…）后  URL=… REPO=<本地仓库，origin 指向临时仓库> node tools/shoot-v032-pr.mjs
// 出图：docs/images/v0.3.2/{pr-card,pr-opened}.jpg
import puppeteer from 'puppeteer-core'
import { mkdirSync } from 'node:fs'
const base = process.env.URL ?? 'http://localhost:1421'
const out = new URL(`../../../docs/images/${process.env.SHOTS ?? 'v0.3.2'}/`, import.meta.url).pathname
mkdirSync(out, { recursive: true })
const REPO = process.env.REPO ?? ''
const TASK = process.env.TASK ?? 'line_count 把空行也算进去了：「床前明月光\\n\\n疑是地上霜\\n」应为 2 行，实际返回 4。帮我修一下。'
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
const calm = async () => {
  await page.mouse.move(1400, 880)
  await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur())
}
const approveAll = () =>
  page.evaluate(() => [...document.querySelectorAll('[data-testid="approval-card"] button')].find((b) => b.textContent === '允许一次')?.click())

await page.goto(`${base}/?source=new`, { waitUntil: 'networkidle0' })
await page.evaluate((repo) => {
  localStorage.clear()
  localStorage.setItem('tw.prefs', JSON.stringify({ permissionMode: 'auto_review', backend: 'none' }))
  localStorage.setItem('tw.core.repo', repo)
}, REPO)
await page.goto(`${base}/?source=new`, { waitUntil: 'networkidle0' })
await page.click('[data-testid="composer"] textarea')
await page.keyboard.type(TASK, { delay: 5 })
await page.click('[data-testid="send"]')
const done = await until(async () => {
  await approveAll()
  return (await page.$$('[data-testid="result-card"]')).length > 0 && !(await page.$('[data-testid="stop"]'))
}, 600_000)
check('出结论卡', done)
const card = await text('[data-testid="result-card"]')
check(`结论：${card.replace(/\s+/g, ' ').slice(0, 90)}`, card.includes('复验通过'))
check('结论卡上有「开 PR」', !!(await page.$('[data-testid="open-pr"]')))
await page.click('[data-testid="open-pr"]')
check('审批卡读出计划', await until(async () => !!(await page.$('[data-testid="pr-plan"]')), 30_000))
const repo = await text('[data-testid="pr-repo"]')
const branch = await text('[data-testid="pr-branch"]')
const title = await text('[data-testid="pr-title"]')
check(`审批卡：${repo} · ${branch} · ${title}`, repo.includes('/') && branch.includes('→') && title.length > 0)
check(`授权方式：${await text('[data-testid="pr-auth"]')}`, !!(await page.$('[data-testid="pr-auth"]')))
await calm()
await wait(500)
await page.screenshot({ path: out + 'pr-card.jpg', type: 'jpeg', quality: 86 })
if (process.env.CONFIRM === '1') {
  await page.click('[data-testid="pr-confirm"]')
  const ok = await until(async () => !!(await page.$('[data-testid="pr-opened"]')) || !!(await page.$('[data-testid="pr-error"]')), 120_000)
  const url = await text('[data-testid="pr-url"]')
  check(`开出 PR：${url || (await text('[data-testid="pr-error"]'))}`, ok && /github\.com\/.+\/pull\/\d+/.test(url))
  console.log(`PR_URL ${url}`)
  await calm()
  await wait(500)
  await page.screenshot({ path: out + 'pr-opened.jpg', type: 'jpeg', quality: 86 })
}
check('无页面错误', errors.filter((e) => !/favicon|DevTools/.test(e)).length === 0)
console.log(results.join('\n'))
if (errors.length) console.log('errors:', errors.slice(0, 5).join('\n'))
await browser.close()
