// 0.2.0 真机反馈（2026-10-11）前后对比截图：BUG1–5、SUGG1–3。
// 用法：TW_DEV_BRIDGE=1 TW_DEMO_DELAY_S=0.3 npx vite --port 1440 后
//   cd tools && URL=http://localhost:1440 PHASE=before|after node shoot-feedback.mjs
// 输出 docs/feedback-2026-10-11/<phase>-*.png，并把可量化的检查写到 <phase>-checks.json
import { mkdirSync, writeFileSync } from 'node:fs'
import puppeteer from 'puppeteer-core'
import { wrapInPage } from './wrap-audit.mjs'
const base = process.env.URL ?? 'http://localhost:1440'
const phase = process.env.PHASE ?? 'after'
const out = new URL('../docs/feedback-2026-10-11/', import.meta.url).pathname
mkdirSync(out, { recursive: true })
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const ONLY = (process.env.ONLY ?? '').split(',').filter(Boolean)
const want = (k) => !ONLY.length || ONLY.includes(k)
const checks = {}

const browser = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox', '--hide-scrollbars'] })
async function open({ theme = 'light', language = 'zh', width = 1280, height = 800, dpr = 1, url = '/?source=fixture:success&speed=40' } = {}) {
  const page = await browser.newPage()
  await page.setViewport({ width, height, deviceScaleFactor: dpr })
  await page.evaluateOnNewDocument(
    (theme, language) => {
      if (!sessionStorage.getItem('seeded')) {
        localStorage.clear()
        localStorage.setItem('tw.prefs', JSON.stringify({ theme, language, name: 'Eva' }))
        sessionStorage.setItem('seeded', '1')
      }
    },
    theme,
    language,
  )
  await page.goto(base + url, { waitUntil: 'networkidle0' })
  await page.waitForSelector('[data-testid="composer"]', { timeout: 15000 })
  await wait(600)
  return page
}
const shot = async (page, name, clip) => {
  await wait(500)
  await page.screenshot({ path: `${out}${phase}-${name}.png`, ...(clip ? { clip } : {}) })
  console.error('shot', `${phase}-${name}.png`)
}
const calm = (page) => page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur()).then(() => page.mouse.move(1270, 790))
const rectOf = (page, sel) => page.evaluate((sel) => {
  const el = document.querySelector(sel)
  if (!el) return null
  const r = el.getBoundingClientRect()
  return { x: r.x, y: r.y, width: r.width, height: r.height }
}, sel)
const overlaps = (a, b) => !!a && !!b && a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height

const wrapAudit = wrapInPage


// ── BUG1：+ 菜单打开时“添加”提示不应出现，也不能盖住菜单
if (want('bug1')) {
  const page = await open()
  await wait(600)
  await page.click('[data-testid="plus-button"]')
  await wait(900)
  const tip = await page.evaluate(() => {
    const t = document.querySelector('[data-testid="plus-button"]')?.closest('.tip-host')?.querySelector('.tip')
    if (!t) return null
    const cs = getComputedStyle(t)
    const r = t.getBoundingClientRect()
    return { opacity: Number(cs.opacity), x: r.x, y: r.y, width: r.width, height: r.height }
  })
  const menu = await rectOf(page, '[data-testid="plus-menu"]')
  checks.bug1 = { tipVisible: !!tip && tip.opacity > 0.05, overlapsMenu: !!tip && tip.opacity > 0.05 && overlaps(tip, menu) }
  const c = await rectOf(page, '[data-testid="composer"]')
  await shot(page, 'bug1-plus-menu-tooltip', { x: Math.max(0, c.x - 20), y: Math.max(0, c.y - 300), width: Math.min(700, c.width + 40), height: c.height + 320 })
  await page.close()
}

// ── BUG2：仓库路径编辑时，模型选择器不能换行
if (want('bug2')) {
  const page = await open({ width: 1024 })
  await page.click('[data-testid="nav-new"]')
  await page.waitForSelector('[data-testid="repo-chip"], [data-testid="repo-input"]', { timeout: 8000 }).catch(() => {})
  const long = 'D:\\Projects\\very-long-folder-name\\another-nested-directory\\triwitness-desktop-app'
  const isInput = await page.$('[data-testid="repo-input"]')
  if (!isInput) await page.click('[data-testid="repo-chip"]').catch(() => {})
  await wait(300)
  if (await page.$('[data-testid="repo-input"]')) {
    await page.click('[data-testid="repo-input"]', { clickCount: 3 })
    await page.type('[data-testid="repo-input"]', long)
  } else if (await page.$('[data-testid="repo-manual"]')) {
    await page.type('[data-testid="repo-manual"]', long)
    await page.keyboard.press('Enter')
  }
  await wait(400)
  const mp = await page.evaluate(() => {
    const el = document.querySelector('[data-testid="model-picker"]')
    if (!el) return null
    // 文字行数：所有文字片段的行顶聚类（按钮自身高度不代表换行）
    const r = document.createRange()
    r.selectNodeContents(el)
    const tops = [...r.getClientRects()].filter((x) => x.width > 0).map((x) => Math.round(x.top + x.height / 2))
    const lines = tops.sort((a, b) => a - b).filter((t, i, a) => i === 0 || t - a[i - 1] > 6).length
    return { height: el.getBoundingClientRect().height, lines }
  })
  await wait(900)
  const c = await rectOf(page, '[data-testid="composer"]')
  await shot(page, 'bug2-repo-editing', { x: c.x - 10, y: Math.max(0, c.y - 260), width: c.width + 20, height: c.height + 270 })
  await calm(page)
  await wait(300)
  const chip = await page.evaluate(() => {
    const el = document.querySelector('[data-testid="repo-chip"]')
    if (!el) return null
    return { height: el.getBoundingClientRect().height, truncated: el.scrollWidth > el.clientWidth || !!el.querySelector('.truncate') }
  })
  await shot(page, 'bug2-repo-chip', { x: c.x - 10, y: c.y - 10, width: c.width + 20, height: c.height + 20 })
  // 再点开 chip：选择文件夹 · 最近 · 手动输入
  let picker = false
  let recent = false
  if (await page.$('[data-testid="repo-chip"]')) {
    await page.click('[data-testid="repo-chip"]')
    await wait(500)
    picker = !!(await page.$('[data-testid="repo-browse"]'))
    recent = !!(await page.$('[data-testid="repo-recent"]'))
    if (picker) await shot(page, 'bug2-repo-menu', { x: c.x - 10, y: Math.max(0, c.y - 300), width: c.width + 20, height: c.height + 310 })
    await calm(page)
  }
  checks.bug2 = { modelPicker: mp, chip, picker, recent }
  await page.close()
}

// ── BUG3：连点“新会话”三次
if (want('bug3')) {
  const page = await open({ url: '/?source=local' })
  const rows0 = await page.$$eval('[data-testid="chat-row"]', (r) => r.length)
  for (let i = 0; i < 3; i++) {
    await page.click('[data-testid="nav-new"]')
    await wait(350)
  }
  const rows1 = await page.$$eval('[data-testid="chat-row"]', (r) => r.length)
  checks.bug3 = { rowsBefore: rows0, rowsAfter3Clicks: rows1, created: rows1 - rows0 }
  await calm(page)
  await shot(page, 'bug3-new-chat-x3', { x: 0, y: 0, width: 640, height: 800 })
  await page.close()
}

// ── BUG4：搜索 vs 会话
if (want('bug4')) {
  const page = await open()
  await page.click('[data-testid="nav-search"]')
  await wait(500)
  checks.bug4 = { searchOpensPalette: !!(await page.$('[data-testid="search-palette"], [data-testid="search-dialog"], [role="dialog"]')) }
  await shot(page, 'bug4-search')
  await page.keyboard.press('Escape')
  await wait(300)
  const chats = await page.$('[data-testid="nav-chats"]')
  if (chats) await chats.click()
  else await page.evaluate(() => [...document.querySelectorAll('[data-testid="sidebar"] button')].find((b) => /会话|Chats/.test(b.textContent ?? '') && !b.dataset.testid)?.click())
  await wait(600)
  checks.bug4.chatsPage = !!(await page.$('[data-testid="chats-page"]'))
  checks.bug4.chatsOpensSameAsSearch = !checks.bug4.chatsPage && !!(await page.$('[role="dialog"]'))
  await shot(page, 'bug4-chats')
  await page.close()
}

// ── BUG5：英文 + 100/125/150% 缩放下的按钮换行
if (want('bug5')) checks.bug5 = {}
if (want('bug5')) for (const [label, width, dpr] of [['100', 1280, 1], ['125', 1024, 1.25], ['150', 853, 1.5]]) {
  for (const language of ['zh', 'en']) {
    const page = await open({ language, width, height: 720, dpr })
    const res = { home: await page.evaluate(wrapAudit) }
    if (label !== '100' || language === 'en') await shot(page, `bug5-${language}-${label}-home`)
    await page.keyboard.down('Control')
    await page.keyboard.press(',')
    await page.keyboard.up('Control')
    await page.waitForSelector('[data-testid="settings"]', { timeout: 5000 }).catch(() => {})
    for (const s of ['general', 'model', 'permissions', 'sandbox']) {
      await page.click(`[data-testid="settings-nav-${s}"]`).catch(() => {})
      await wait(300)
      res[s] = await page.evaluate(wrapAudit)
    }
    if (language === 'en') await shot(page, `bug5-en-${label}-settings`)
    checks.bug5[`${language}-${label}`] = res
    await page.close()
  }
}

// ── SUGG1：权限模式
if (want('sugg1')) {
  const page = await open()
  await page.keyboard.down('Control')
  await page.keyboard.press(',')
  await page.keyboard.up('Control')
  await page.waitForSelector('[data-testid="settings"]')
  await page.click('[data-testid="settings-nav-permissions"]')
  await wait(500)
  checks.sugg1 = { modes: await page.$$eval('[data-testid^="perm-"][role="radio"]', (b) => b.map((x) => x.getAttribute('data-testid'))) }
  await shot(page, 'sugg1-permission-modes')
  await page.close()
}

// ── SUGG2：侧栏会话行悬停高度
if (want('sugg2')) {
  const page = await open({ url: '/?source=local' })
  const rows = await page.$$('[data-testid="chat-row"]')
  const h = async () => page.evaluate(() => [...document.querySelectorAll('[data-testid="chat-row"]')].map((r) => Math.round(r.getBoundingClientRect().height * 10) / 10))
  const before = await h()
  if (rows[0]) await rows[0].hover()
  await wait(500)
  const hover = await h()
  checks.sugg2 = { rowHeights: before.slice(0, 5), hoverHeights: hover.slice(0, 5), changed: before.some((x, i) => x !== hover[i]) }
  await shot(page, 'sugg2-row-hover', { x: 0, y: 0, width: 320, height: 520 })
  await page.close()
}

// ── SUGG3：配色（浅色 / 深色）
if (want('sugg3')) for (const theme of ['light', 'dark']) {
  const page = await open({ theme, width: 1280, height: 800 })
  await calm(page)
  await shot(page, `sugg3-palette-${theme}-chat`)
  await page.click('[data-testid="nav-new"]')
  await wait(500)
  await calm(page)
  await shot(page, `sugg3-palette-${theme}-home`)
  await page.close()
}

await browser.close()
let prev = {}
try {
  prev = JSON.parse((await import('node:fs')).readFileSync(`${out}${phase}-checks.json`, 'utf8'))
} catch {}
writeFileSync(`${out}${phase}-checks.json`, JSON.stringify({ ...prev, ...checks }, null, 2))
console.log(JSON.stringify(checks, null, 1))
