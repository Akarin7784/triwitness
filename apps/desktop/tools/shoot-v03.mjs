// v0.3 预览：README 截图 + 冒烟（打包核心 / 演示适配器，¥0）
// 用法：TW_DEV_BRIDGE=1 TW_CORE='["<onedir>/tw"]' npm run dev 后  node tools/shoot-v03.mjs
// 出图：docs/images/v0.3/{main,approval,result,budget,ledger,about}.jpg（纸色主题）
import puppeteer from 'puppeteer-core'
const base = process.env.URL ?? 'http://localhost:1420'
const out = new URL('../../../docs/images/v0.3/', import.meta.url).pathname
const browser = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox', '--hide-scrollbars'] })
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const results = []
const check = (name, ok) => results.push(`${ok ? 'PASS' : 'FAIL'}  ${name}`)
const page = await browser.newPage()
const errors = []
page.on('pageerror', (e) => errors.push(String(e)))
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1.5 })
const text = (sel) => page.$eval(sel, (el) => el.textContent?.trim() ?? '').catch(() => '')
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

await page.goto(`${base}/?source=fixture:success&speed=8`, { waitUntil: 'networkidle0' })
await page.evaluate(() => localStorage.clear())
await page.reload({ waitUntil: 'networkidle0' })

// 新会话 → 演示仓库 → 询问模式下会出审批卡
await page.evaluate(() => [...document.querySelectorAll('button')].find((b) => b.textContent?.includes('新会话'))?.click())
await until(() => page.$('[data-testid="repo-chip"]').then(Boolean), 5000)
await calm()
await page.screenshot({ path: out + 'main.jpg', type: 'jpeg', quality: 86 })
await page.click('[data-testid="send"]')
check('任务已起', await until(() => page.evaluate(() => /live(%3A|:)/.test(location.search)), 20_000))
let shotApproval = false
const done = await until(async () => {
  if (await page.$('[data-testid="result-card"]')) return true
  if (await page.$('[data-testid="approval-card"]')) {
    if (!shotApproval) {
      await calm()
      await wait(800)
      await page.screenshot({ path: out + 'approval.jpg', type: 'jpeg', quality: 86 })
      shotApproval = true
    }
    await page.evaluate(() =>
      [...document.querySelectorAll('[data-testid="approval-card"] button')].find((b) => b.textContent === '允许一次')?.click(),
    )
    await wait(600)
  }
  return false
}, 120_000)
check('结论卡出现', done)
await wait(2500)
const card = await text('[data-testid="result-card"]')
check('结论卡如实表述交付（本地分支 + PR 说明，未在 GitHub 上创建 PR）', card.includes('没有在 GitHub 上创建 PR') && card.includes('复制 PR 说明'))
check('不再出现“开 PR / PR 已开”', !(await page.evaluate(() => /PR 已开|打开 PR|创建 PR(?!。)/.test(document.body.innerText))))
await page.evaluate(() => document.querySelector('[data-testid="result-card"]')?.scrollIntoView({ block: 'end' }))
await calm()
await wait(600)
await page.screenshot({ path: out + 'result.jpg', type: 'jpeg', quality: 86 })

// 设置 → 预算：真实账本
await page.goto(`${base}/?view=settings`, { waitUntil: 'networkidle0' })
await page.click('[data-testid="settings-nav-budget"]')
check('预算页读到真实账本', await until(async () => (await text('[data-testid="budget-spent"]')).includes('¥'), 20_000))
check(`账本摘要：${await text('[data-testid="ledger-summary"]')}`, (await text('[data-testid="ledger-summary"]')).includes('次调用'))
const sb = await text('footer')
check(`状态栏余额来自账本（${sb.replace(/\s+/g, ' ')}）`, /¥\d+\.\d\d/.test(sb) && sb.includes('v0.3.0-preview'))
await calm()
await page.screenshot({ path: out + 'budget.jpg', type: 'jpeg', quality: 86 })
await page.evaluate(() => document.querySelector('[data-testid="ledger-card"]')?.scrollIntoView({ block: 'start' }))
await wait(400)
await page.screenshot({ path: out + 'ledger.jpg', type: 'jpeg', quality: 86 })

await page.click('[data-testid="settings-nav-about"]')
await wait(500)
check('关于页：检查更新 = 打开发布页', (await text('[data-testid="check-updates"]')).includes('打开发布页'))
check('关于页版本 0.3.0-preview', await page.evaluate(() => document.body.innerText.includes('v0.3.0-preview')))
await calm()
await page.screenshot({ path: out + 'about.jpg', type: 'jpeg', quality: 86 })

await browser.close()
console.log(results.join('\n'))
console.log(errors.length ? `console errors:\n${errors.join('\n')}` : 'no console errors')
process.exit(results.some((r) => r.startsWith('FAIL')) ? 1 : 0)
