// UI-20：Claude 式对话流 / 输入框 / 模型选择的端到端冒烟 + 截图（真实核心 · 演示适配器 · ¥0）
// 用法：TW_DEV_BRIDGE=1 TW_DEMO_DELAY_S=1.4 npm run dev 后  cd tools && node shoot-chat.mjs
import puppeteer from 'puppeteer-core'
const base = process.env.URL ?? 'http://localhost:1420'
const out = new URL('../docs/', import.meta.url).pathname
const browser = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox', '--hide-scrollbars'] })
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const results = []
const check = (name, ok) => results.push(`${ok ? 'PASS' : 'FAIL'}  ${name}`)
const page = await browser.newPage()
const errors = []
page.on('pageerror', (e) => errors.push(String(e)))
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 })
const has = (sel) => page.$(sel).then(Boolean)
const text = (sel) => page.$eval(sel, (el) => el.textContent?.trim() ?? '').catch(() => '')
const until = async (fn, ms = 60_000) => {
  const t0 = Date.now()
  while (Date.now() - t0 < ms) {
    if (await fn()) return true
    await wait(150)
  }
  return false
}
const calm = async () => {
  await page.mouse.move(1100, 300)
  await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur())
}
const clickText = (sel, t) =>
  page.evaluate((sel, t) => [...document.querySelectorAll(sel)].find((b) => b.textContent?.includes(t))?.click(), sel, t)

await page.goto(`${base}/?source=fixture:success&speed=8`, { waitUntil: 'networkidle0' })
await page.evaluate(() => localStorage.clear())
await page.reload({ waitUntil: 'networkidle0' })

// 1) 新会话 + 输入框
await clickText('button', '新会话')
// 演示模式可空发：发送位是发送键；其他模式空输入时是语音键
check('输入框：+ / 模型 / 发送位', (await has('[data-testid="plus-button"]')) && (await has('[data-testid="model-picker"]')) &&
  ((await has('[data-testid="mic"]')) || (await has('[data-testid="send"]'))))
await page.click('textarea[aria-label="输入"]')
await page.keyboard.type('line_count 把空行也算进去了')
await page.keyboard.down('Shift')
await page.keyboard.press('Enter')
await page.keyboard.up('Shift')
await page.keyboard.type('「床前明月光\\n\\n疑是地上霜\\n」应为 2 行')
const h = await page.$eval('textarea[aria-label="输入"]', (el) => el.getBoundingClientRect().height)
check(`Shift+Enter 换行、自动增高 (${Math.round(h)}px)`, h > 50)
check('有字时出现发送键', await has('[data-testid="send"]'))

// 2) 模型选择 + 思考强度
await page.click('[data-testid="model-picker"]')
await until(() => has('[data-testid="model-menu"]'), 3000)
const menu = await text('[data-testid="model-menu"]')
check('模型菜单：只有 Flash 可选、无 v4-pro', menu.includes('DeepSeek Flash') && !/v4-pro/i.test(menu) && menu.includes('稍后'))
await page.hover('[data-testid="effort-item"]')
await until(() => has('[data-testid="effort-menu"]'), 3000)
await wait(450)
await page.screenshot({ path: out + 'composer-model-picker.png' })
await clickText('[data-testid="effort-menu"] button', '高')
await wait(300)
check(`思考强度持久化 (${await text('[data-testid="model-picker"]')})`, (await text('[data-testid="model-picker"]')).includes('思考 高') &&
  (await page.evaluate(() => JSON.parse(localStorage.getItem('tw.prefs') ?? '{}').thinking)) === 'high')

// 3) + 菜单（入口齐全，未做的给“即将推出”）
await page.click('[data-testid="plus-button"]')
await until(() => has('[data-testid="plus-menu"]'), 3000)
await wait(400)
await page.screenshot({ path: out + 'composer-plus-menu.png' })
await clickText('[data-testid="plus-menu"] button', '网页搜索')
check('未做的入口：即将推出', await until(async () => (await text('[data-testid="toast"]')).includes('即将推出'), 3000))
await wait(2600)

// 4) 草稿按会话保存：切走再切回
await clickText('[data-testid="chat-row"]', '#87')
await wait(500)
await clickText('[data-testid="chat-row"]', '新会话')
await wait(300)

// 发送
await page.evaluate(() => {
  const ta = document.querySelector('textarea[aria-label="输入"]')
  ta?.focus()
})
const draft = await page.$eval('textarea[aria-label="输入"]', (el) => el.value)
check(`草稿按会话保存（${draft.length} 字）`, draft.includes('line_count'))
if (!draft) {
  await page.click('textarea[aria-label="输入"]')
  await page.keyboard.type('line_count 把空行也算进去了，帮我修一下')
}
await page.keyboard.press('Enter')
check('任务已起', await until(() => page.evaluate(() => location.search.includes('live')), 20_000))

// 5) 思考块流式
check('思考块出现（思考中）', await until(async () => (await text('[data-testid="thinking-block"]')).includes('思考中'), 30_000))
await until(async () => (await page.$eval('[data-testid="thinking-block"]', (el) => el.textContent.length).catch(() => 0)) > 30, 10_000)
await calm()
await page.screenshot({ path: out + 'thinking-streaming.png' })

// 6) 正文流式到一半
check('正文流式（软光标）', await until(() => has('[data-testid="streaming-text"] .caret-ink'), 30_000))
await until(async () => (await page.$$('[data-testid="tool-row"]')).length >= 1 && (await has('[data-testid="streaming-text"]')), 30_000)
await calm()
await page.screenshot({ path: out + 'streaming-mid-message.png' })
check('思考块收成“思考了 N 秒”', (await text('[data-testid="thinking-block"]')).includes('思考了'))

// 7) 审批 → 结论
check('审批卡', await until(() => has('[data-testid="approval-card"]'), 90_000))
await clickText('[data-testid="approval-card"] button', '允许一次')
check('结论卡', await until(() => has('[data-testid="result-card"]'), 120_000))
const rows = await page.$$('[data-testid="tool-row"]')
check(`工具行 ${rows.length} 条`, rows.length >= 7)
if (rows[1]) await rows[1].click()
await wait(500)
const md = await page.$$eval('.md-code', (els) => els.length)
check(`Markdown 代码块（带复制）${md}`, md >= 1)
check('消息操作条（复制 / 重试 / 反馈）', await has('[data-testid="message-actions"]'))
await page.evaluate(() => {
  const el = document.querySelector('[data-testid="chat-scroll"]')
  el.scrollTop = 0
  el.dispatchEvent(new Event('scroll'))
})
await page.evaluate(() => {
  const el = document.querySelector('[data-testid="chat-scroll"]')
  const tool = [...document.querySelectorAll('[data-testid="tool-row"]')][1]
  el.scrollTop = Math.max(0, tool.offsetTop - 220)
})
await calm()
await wait(600)
await page.screenshot({ path: out + 'chat-tool-rows.png' })
check('上翻后出现“回到底部”', await until(() => has('[data-testid="jump-bottom"]'), 3000))
await page.click('[data-testid="jump-bottom"]')
check('点了回到底部', await until(async () => !(await has('[data-testid="jump-bottom"]')), 3000))
await calm()
await wait(800)
await page.screenshot({ path: out + 'chat-result.png' })

check(`无页面错误 (${errors.length}${errors.length ? '：' + errors.slice(0, 3).join(' | ') : ''})`, errors.length === 0)
console.log(results.join('\n'))
await browser.close()
process.exit(results.some((r) => r.startsWith('FAIL')) ? 1 : 0)
