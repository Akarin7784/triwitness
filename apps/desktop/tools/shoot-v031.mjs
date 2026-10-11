// v0.3.1：对话轮 e2e + 截图（开发桥 + 打包核心；模型走真实适配器 → TW_LLM_BASE_URL_OVERRIDE 指向的服务）
// 用法：TW_DEV_BRIDGE=1 TW_CORE='["<onedir>/tw"]' npm run dev 后  REPO=<verses 仓库> node tools/shoot-v031.mjs
// 出图：docs/images/v0.3.1/{hello,followup,task-ask,task-result}.jpg
import puppeteer from 'puppeteer-core'
import { mkdirSync } from 'node:fs'
const base = process.env.URL ?? 'http://localhost:1420'
const out = new URL(`../../../docs/images/${process.env.SHOTS ?? 'v0.3.1'}/`, import.meta.url).pathname
mkdirSync(out, { recursive: true })
const REPO = process.env.REPO ?? ''
const TASK = process.env.TASK ?? 'line_count 把空行也算进去了：「床前明月光\\n\\n疑是地上霜\\n」应为 2 行，实际返回 4。帮我修一下。'
const MODE = process.env.MODE ?? 'ask'
// 额外偏好（真实 key 跑时：ALLOW_PEAK=1 MAX_COST=0.5 BACKEND=none）；ONLY=chat|task 只跑一部分
const EXTRA = {
  ...(process.env.ALLOW_PEAK === '1' ? { allowPeak: true } : {}),
  ...(process.env.MAX_COST ? { maxCost: Number(process.env.MAX_COST) } : {}),
  ...(process.env.BACKEND ? { backend: process.env.BACKEND } : {}),
}
const ONLY = process.env.ONLY ?? ''
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
const body = () => page.evaluate(() => document.body.innerText)
const send = async (text) => {
  await page.click('[data-testid="composer"] textarea')
  await page.keyboard.type(text, { delay: 5 })
  await page.click('[data-testid="send"]')
}
const turnDone = (n) =>
  until(async () => (await page.$$('[data-testid="message-actions"]')).length >= n && !(await page.$('[data-testid="stop"]')), 120_000)

// 正式版行为：开发构建也默认真实模式；清空本地状态，从一个新会话开始（不选仓库）
await page.goto(`${base}/?source=new`, { waitUntil: 'networkidle0' })
await page.evaluate((mode, extra) => {
  localStorage.clear()
  localStorage.setItem('tw.prefs', JSON.stringify({ permissionMode: mode, ...extra }))
}, MODE, EXTRA)
await page.goto(`${base}/?source=new`, { waitUntil: 'networkidle0' })
check('没有「演示」字样', !(await body()).includes('演示'))

if (ONLY !== 'task') {
// 1) 你好 → 直接回复：没有工具行、结果卡、产物
await send('你好')
check('已起一轮', await until(() => page.evaluate(() => /live(%3A|:)/.test(location.search)), 20_000))
check('回复结束', await turnDone(1))
check('没有结果卡', !(await page.$('[data-testid="result-card"]')))
check('没有工具行', !(await page.$('[data-testid="tool-row"]')))
const hello = await page.$eval('[data-testid="assistant-turn"]', (el) => el.textContent ?? '').catch(() => '')
check(`回复：${hello.slice(0, 80)}`, hello.length > 0)
check('状态不是「已完成」任务', !(await page.evaluate(() => document.querySelector('header')?.textContent?.includes('已完成'))))
await calm()
await wait(500)
await page.screenshot({ path: out + 'hello.jpg', type: 'jpeg', quality: 86 })

// 2) 多轮：跟进同一会话，带上一轮历史
await send('我刚才说了什么？')
check('第二轮结束', await turnDone(2))
check('上一轮仍显示在上面', !!(await page.$('[data-testid="past-turn"]')))
const turns = await page.$$eval('[data-testid="assistant-turn"]', (els) => els.map((e) => e.textContent ?? ''))
check(`跟进回复：${(turns.at(-1) ?? '').slice(0, 80)}`, (turns.at(-1) ?? '').includes('你好'))
await calm()
await wait(500)
await page.screenshot({ path: out + 'followup.jpg', type: 'jpeg', quality: 86 })

}

// 3) 小任务：新会话 + 仓库
if (REPO && ONLY !== 'chat') {
  await page.evaluate((repo) => localStorage.setItem('tw.core.repo', repo), REPO)
  await page.goto(`${base}/?source=new`, { waitUntil: 'networkidle0' })
  await send(TASK)
  let shot = false
  const done = await until(async () => {
    if (await page.$('[data-testid="result-card"]')) return true
    if (await page.$('[data-testid="approval-card"]')) {
      if (!shot) {
        await calm()
        await wait(600)
        await page.screenshot({ path: out + `task-${MODE}-approval.jpg`, type: 'jpeg', quality: 86 })
        shot = true
      }
      await page.evaluate(() =>
        [...document.querySelectorAll('[data-testid="approval-card"] button')].find((b) => b.textContent === '允许一次')?.click(),
      )
      await wait(500)
    }
    return false
  }, 600_000)
  check(`任务结论卡（${MODE}）`, done)
  await wait(2000)
  const card = await page.$eval('[data-testid="result-card"]', (el) => el.textContent ?? '').catch(() => '')
  check(`结论：${card.replace(/\s+/g, ' ').slice(0, 100)}`, card.length > 0)
  const cost = await page.$eval('[data-testid="result-cost"]', (el) => `${el.textContent} | ${el.getAttribute('title')}`).catch(() => '')
  console.log(`COST ${cost}`)
  await page.evaluate(() => document.querySelector('[data-testid="result-card"]')?.scrollIntoView({ block: 'end' }))
  await calm()
  await wait(500)
  await page.screenshot({ path: out + `task-${MODE}.jpg`, type: 'jpeg', quality: 86 })
}

check(`没有页面错误（${errors.length}）`, errors.length === 0)
if (errors.length) console.log(errors.slice(0, 5).join('\n'))
console.log(results.join('\n'))
await browser.close()
process.exit(results.some((r) => r.startsWith('FAIL')) ? 1 : 0)
