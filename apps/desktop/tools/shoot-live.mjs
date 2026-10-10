// UI-10：桌面端驱动真实 Python 核心（演示适配器，¥0）的端到端冒烟 + 截图
// 用法：TW_DEV_BRIDGE=1 TW_DEMO_DELAY_S=1.2 npm run dev 后  node tools/shoot-live.mjs
// 流程：新会话 → 发送（演示仓库）→ 实时推流 → 审批卡 → 允许一次 → 结论卡；再起一个任务中途停止；刷新后续上。
import puppeteer from 'puppeteer-core'
const base = process.env.URL ?? 'http://localhost:1420'
const out = new URL('../docs/', import.meta.url).pathname
const browser = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox', '--hide-scrollbars'] })
const calm = async () => {
  await page.mouse.move(700, 400)
  await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur())
}
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const results = []
const check = (name, ok) => results.push(`${ok ? 'PASS' : 'FAIL'}  ${name}`)

const page = await browser.newPage()
const errors = []
page.on('pageerror', (e) => errors.push(String(e)))
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 })
const text = (sel) => page.$eval(sel, (el) => el.textContent?.trim() ?? '').catch(() => '')
const chip = (id) => text(`[data-testid="${id}"]`)
const until = async (fn, ms = 60_000) => {
  const t0 = Date.now()
  while (Date.now() - t0 < ms) {
    if (await fn()) return true
    await wait(400)
  }
  return false
}
// 推流区（右栏）每行一个 .selectable.font-mono；审批卡里那一行不算
const streamLen = () =>
  page.$$eval('.selectable.font-mono', (els) =>
    els.filter((e) => !e.closest('[data-testid]')).reduce((n, e) => n + (e.textContent?.length ?? 0), 0),
  )
const newTask = async () => {
  await page.evaluate(() => [...document.querySelectorAll('button')].find((b) => b.textContent?.includes('新会话'))?.click())
  check('新会话显示仓库签', await until(() => page.$('[data-testid="repo-chip"]').then(Boolean), 5000))
  await page.click('[data-testid="send"]')
  check('任务已起（URL 切到 live:）', await until(() => page.evaluate(() => location.search.includes('live%3A') || location.search.includes('live:')), 20_000))
}

await page.goto(`${base}/?source=fixture:success&speed=8`, { waitUntil: 'networkidle0' })
await page.evaluate(() => localStorage.clear())
await page.reload({ waitUntil: 'networkidle0' })

// 1) 起任务 → 实时推流
await newTask()
check('实时推流在写', await until(async () => (await streamLen()) > 150, 30_000))
await calm()
await page.screenshot({ path: out + 'live-stream.png' })

// 2) 审批卡（核心在等 submit_repro 的复现命令）
check('审批卡出现', await until(() => page.$('[data-testid="approval-card"]').then(Boolean), 60_000))
await until(async () => (await chip('state-chip')).includes('待批'), 15_000)
check(`状态签 = 待批 (${await chip('state-chip')})`, (await chip('state-chip')).includes('待批'))
await calm()
await wait(1200)
await page.screenshot({ path: out + 'approval-card.png' })
const cardText = await text('[data-testid="approval-card"]')
check('审批卡有四个选择', ['允许一次', '本次任务', '总是', '拒绝'].every((s) => cardText.includes(s)))
await page.evaluate(() =>
  [...document.querySelectorAll('[data-testid="approval-card"] button')].find((b) => b.textContent === '允许一次')?.click(),
)
check('允许后审批卡收起', await until(() => page.$('[data-testid="approval-card"]').then((x) => !x), 15_000))

// 3) 结论卡
check('结论卡出现', await until(() => page.$('[data-testid="result-card"]').then(Boolean), 90_000))
await until(async () => (await chip('state-chip')).includes('完成'), 30_000)
await calm()
await wait(2500)
const result = await text('[data-testid="result-card"]')
check(`结论：${result.slice(0, 40)}…`, result.includes('复验通过') && /风险 L[0-3]/.test(result) && result.includes('pr.md'))
check(`状态签 = ${await chip('state-chip')}，费用 = ${await chip('cost-chip')}`, (await chip('state-chip')).includes('完成') && (await chip('cost-chip')).startsWith('¥0.000'))
await page.screenshot({ path: out + 'result.png' })
const doneUrl = page.url()

// 4) 停止
await newTask()
await until(async () => (await streamLen()) > 60, 30_000)
check('进行中显示停止键', await page.$('[data-testid="stop"]').then(Boolean))
await page.click('[data-testid="stop"]')
check('停止后结论卡 = 已停止', await until(async () => (await text('[data-testid="result-card"]')).includes('已停止'), 30_000))
await calm()
await wait(1500)
await page.screenshot({ path: out + 'stopped.png' })

// 5) 刷新后续上（读 run_dir/trajectory.jsonl + 存下的结论）
await page.goto(doneUrl, { waitUntil: 'networkidle0' })
check('续上：推流恢复', await until(async () => (await streamLen()) > 120, 30_000))
check('续上：结论卡恢复（笔写完后）', await until(() => page.$('[data-testid="result-card"]').then(Boolean), 120_000))
const side = await page.evaluate(() => document.querySelector('aside')?.textContent ?? '')
check('侧栏列出两个真实任务', (side.match(/演示任务/g) ?? []).length >= 2)

check(`无页面错误 (${errors.length}${errors.length ? '：' + errors.join(' | ') : ''})`, errors.length === 0)
console.log(results.join('\n'))
await browser.close()
process.exit(results.some((r) => r.startsWith('FAIL')) ? 1 : 0)
