// UI-09：三份 golden fixture 的回放截图 + 冒烟检查（真实时间等待，rAF 在虚拟时间下不走）
// 用法：npm run dev 后  node tools/shoot-replay.mjs
import puppeteer from 'puppeteer-core'
const base = process.env.URL ?? 'http://localhost:1420'
const out = new URL('../docs/', import.meta.url).pathname
const speed = process.env.SPEED ?? '4'
const browser = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox', '--hide-scrollbars'] })
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const results = []
const check = (name, ok) => results.push(`${ok ? 'PASS' : 'FAIL'}  ${name}`)
const terminal = { success: '完成', failure: '失败', budget_exceeded: '预算' }

const page = await browser.newPage()
const errors = []
page.on('pageerror', (e) => errors.push(String(e)))
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 })
const chip = (id) => page.$eval(`[data-testid="${id}"]`, (el) => el.textContent?.trim() ?? '').catch(() => '')

for (const name of Object.keys(terminal)) {
  await page.goto(`${base}/?source=fixture:${name}&speed=${speed}`, { waitUntil: 'networkidle0' })
  await wait(6000)
  if (name === 'success') await page.screenshot({ path: out + 'replay-success-mid.png' })
  const t0 = Date.now()
  while (Date.now() - t0 < 120_000 && !(await chip('state-chip')).includes(terminal[name])) await wait(1000)
  await wait(2500) // 让最后一行落笔、墨色沉下去
  const state = await chip('state-chip')
  const cost = await chip('cost-chip')
  check(`${name}: 状态 chip = ${state}，费用 chip = ${cost}`, state.includes(terminal[name]) && cost.startsWith('¥'))
  await page.screenshot({ path: out + `replay-${name}.png` })
  if (name === 'budget_exceeded') {
    await page.hover('[data-testid="cost-chip"]')
    await wait(900)
    await page.screenshot({ path: out + 'replay-budget-tooltip.png', clip: { x: 300, y: 0, width: 1140, height: 200 } })
  }
}

// 暂停 / 继续：暂停期间字数与状态冻结，继续后接着写，不跳字
await page.goto(`${base}/?source=fixture:success&speed=${speed}`, { waitUntil: 'networkidle0' })
await wait(4000)
const streamText = () => page.$eval('.selectable.font-mono', (el) => el.textContent ?? '')
await page.click('button[aria-label="暂停"]').catch(() => errors.push('no pause button'))
await wait(300)
const a = await streamText()
const sa = await chip('state-chip')
await wait(2500)
const b = await streamText()
check(`暂停后冻结 (${a.length} → ${b.length} 字，状态 ${sa})`, a === b && sa === (await chip('state-chip')))
await page.click('button[aria-label="继续"]').catch(() => errors.push('no resume button'))
await wait(2500)
const c = await streamText()
check(`继续后接着写且不跳字 (${b.length} → ${c.length})`, c.length > b.length && c.startsWith(b.slice(0, -1)))

// mock 源仍可用
await page.goto(`${base}/?source=mock&speed=${speed}`, { waitUntil: 'networkidle0' })
await wait(3000)
check('mock 源可回放', (await streamText()).length > 0)

check(`无页面错误 (${errors.length})`, errors.length === 0)
console.log(results.join('\n'))
if (errors.length) console.log(errors.slice(0, 5).join('\n'))
await browser.close()
process.exit(results.some((r) => r.startsWith('FAIL')) ? 1 : 0)
