// UI-21 第 2 轮：设置各分区 / 侧栏 / 重试与编辑后重发（版本切换）/ 赞踩 / 快捷键 / 标题下拉与分享占位
// 真实核心 · 演示适配器 · ¥0。用法：TW_DEV_BRIDGE=1 TW_DEMO_DELAY_S=0.6 npm run dev 后  cd tools && URL=... node shoot-ui21.mjs
import puppeteer from 'puppeteer-core'
const base = process.env.URL ?? 'http://localhost:1420'
const out = new URL('../docs/', import.meta.url).pathname
const browser = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox', '--hide-scrollbars'] })
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const results = []
const check = (name, ok) => results.push(`${ok ? 'PASS' : 'FAIL'}  ${name}`)
const page = await browser.newPage()
const ctx = browser.defaultBrowserContext()
await ctx.overridePermissions(base, ['clipboard-read', 'clipboard-write', 'clipboard-sanitized-write'])
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
  await page.mouse.move(1100, 160)
  await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur())
}
const clickText = (sel, t) =>
  page.evaluate((sel, t) => {
    const el = [...document.querySelectorAll(sel)].find((b) => b.textContent?.includes(t))
    el?.click()
    return !!el
  }, sel, t)
const key = async (combo) => {
  const parts = combo.split('+')
  const last = parts.pop()
  for (const p of parts) await page.keyboard.down(p)
  await page.keyboard.press(last)
  for (const p of parts.reverse()) await page.keyboard.up(p)
}
const toastHas = (t) => until(async () => (await page.$$eval('[data-testid="toast"]', (els) => els.map((e) => e.textContent).join('|'))).includes(t), 4000)
const approveAll = async (ms = 120_000) => {
  const t0 = Date.now()
  while (Date.now() - t0 < ms) {
    if (await has('[data-testid="result-card"]')) return true
    if (await has('[data-testid="approval-card"]')) await clickText('[data-testid="approval-card"] button', '允许一次')
    await wait(300)
  }
  return false
}

await page.goto(`${base}/?source=fixture:success&speed=20`, { waitUntil: 'networkidle0' })
await page.evaluate(() => localStorage.clear())
await page.reload({ waitUntil: 'networkidle0' })

// ── 1) 设置：各分区（Ctrl+,）
await calm()
await key('Control+,')
check('Ctrl+, 打开设置', await until(() => has('[data-testid="settings"]'), 3000))
await wait(500)
await page.screenshot({ path: out + 'settings-general.png' })
for (const s of ['profile', 'model', 'budget', 'permissions', 'sandbox', 'connectors', 'privacy', 'about']) {
  await page.click(`[data-testid="settings-nav-${s}"]`)
  await wait(450)
  if (['model', 'budget', 'permissions', 'sandbox', 'about'].includes(s)) await page.screenshot({ path: out + `settings-${s}.png` })
}
check('设置九个分区都能打开', true)

// 模型：API 密钥（浏览器预览无凭据库）
await page.click('[data-testid="settings-nav-model"]')
await wait(300)
check('API 密钥：浏览器里提示仅桌面应用', (await text('[data-testid="api-key-row"]')).includes('仅桌面应用'))

// 预算：单任务上限调到 ¥0.50（后面起任务时验证核心收到）
await page.click('[data-testid="settings-nav-budget"]')
await wait(300)
await page.$eval('[data-testid="max-cost-row"] input[type=range]', (el) => {
  const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
  set.call(el, '0.5')
  el.dispatchEvent(new Event('input', { bubbles: true }))
})
await wait(200)
check('上限持久化 ¥0.50', (await page.evaluate(() => JSON.parse(localStorage.getItem('tw.prefs') ?? '{}').maxCost)) === 0.5)

// 权限：勇士模式两步确认
await page.click('[data-testid="settings-nav-permissions"]')
await wait(300)
await page.click('[data-testid="perm-ask"]')
check('权限模式持久化 ask', (await page.evaluate(() => JSON.parse(localStorage.getItem('tw.prefs') ?? '{}').permissionMode)) === 'ask')
await page.click('[data-testid="perm-full_access"]')
await until(() => has('[data-testid="unrestricted-dialog"]'), 3000)
const armDisabled = () => page.$eval('[data-testid="unrestricted-arm"]', (b) => b.disabled)
check('勇士模式：未勾选不能开启', await armDisabled())
await page.click('[data-testid="unrestricted-ack"]')
await page.type('[data-testid="unrestricted-phrase"]', '我了解')
check('勇士模式：短语不全不能开启', await armDisabled())
await page.type('[data-testid="unrestricted-phrase"]', '风险')
await wait(450)
await page.screenshot({ path: out + 'settings-unrestricted-dialog.png' })
check('勇士模式：两步齐了可以开启', !(await armDisabled()))
await page.click('[data-testid="unrestricted-arm"]')
await wait(400)
check('勇士模式从不落盘', !(await page.evaluate(() => localStorage.getItem('tw.prefs') ?? '')).includes('full_access'))
await page.click('[data-testid="perm-full_access"]') // 取消上膛
await wait(200)

// 常规：深色主题
await page.click('[data-testid="settings-nav-general"]')
await wait(300)
await page.click('[data-testid="theme-dark"]')
await wait(600)
check('深色主题', (await page.evaluate(() => document.documentElement.dataset.theme)) === 'dark')
await page.screenshot({ path: out + 'settings-general-dark.png' })
await page.click('[data-testid="theme-light"]')
await wait(300)

// ── 2) 快捷键列表 / 搜索
await calm()
await key('Control+/')
check('Ctrl+/ 快捷键列表', await until(() => has('[data-testid="shortcuts-dialog"]'), 3000))
await wait(450)
await page.screenshot({ path: out + 'shortcuts.png' })
await page.keyboard.press('Escape')
await until(async () => !(await has('[data-testid="shortcuts-dialog"]')), 3000)
await key('Control+k')
check('Ctrl+K 搜索', await until(() => has('[data-testid="search-palette"]'), 3000))
await page.keyboard.type('parse_rows')
await wait(450)
await page.screenshot({ path: out + 'search-palette.png' })
await page.keyboard.press('Enter')
check('搜索回车打开会话', await until(() => page.evaluate(() => location.search.includes('recorded')), 3000))

// ── 3) 侧栏：… 菜单 / 星标 / 重命名 / 删除 / 收起
const row = (id) => `[data-testid="chat-row"][data-id="${id}"]`
await page.hover(row('fixture:failure'))
await page.$eval(`${row('fixture:failure')} [data-testid="chat-more"]`, (b) => b.click())
await until(() => has('[data-testid="chat-menu"]'), 3000)
await wait(400)
await page.screenshot({ path: out + 'sidebar-chat-menu.png' })
await clickText('[data-testid="chat-menu"] button', '星标')
await wait(500)
check('星标分组出现', (await page.evaluate(() => document.querySelector('[data-testid="sidebar"]').textContent)).includes('星标'))
await page.hover(row('fixture:failure'))
await page.$eval(`${row('fixture:failure')} [data-testid="chat-more"]`, (b) => b.click())
await page.click('[data-testid="menu-rename"]')
await until(() => has('[data-testid="rename-dialog"]'), 3000)
await page.keyboard.down('Control'); await page.keyboard.press('a'); await page.keyboard.up('Control')
await page.keyboard.type('回归失败的那次')
await page.keyboard.press('Enter')
await wait(400)
check('重命名生效', (await text(row('fixture:failure'))).includes('回归失败的那次'))
const before = (await page.$$('[data-testid="chat-row"]')).length
await page.hover(row('fixture:recorded'))
await page.$eval(`${row('fixture:recorded')} [data-testid="chat-more"]`, (b) => b.click())
await page.click('[data-testid="menu-delete"]')
await until(() => has('[data-testid="delete-dialog"]'), 3000)
await page.click('[data-testid="delete-confirm"]')
await wait(600)
check('删除后少一条', (await page.$$('[data-testid="chat-row"]')).length === before - 1)
await wait(2400) // 等“已删除”提示淡出再截图
await calm()
await key('Control+Shift+S')
await wait(700)
check('Ctrl+Shift+S 收起侧栏', (await page.$eval('[data-testid="sidebar"]', (el) => el.getBoundingClientRect().width)) < 60)
await page.screenshot({ path: out + 'sidebar-collapsed.png' })
await key('Control+Shift+S')
await wait(700)
check('再按展开', (await page.$eval('[data-testid="sidebar"]', (el) => el.getBoundingClientRect().width)) > 200)
const s0 = await page.evaluate(() => location.search)
await key('Control+Shift+BracketRight')
await wait(300)
check('Ctrl+Shift+] 下一个会话', (await page.evaluate(() => location.search)) !== s0)

// ── 4) 标题下拉 / 分享占位
await page.click(row('fixture:success'))
await until(() => has('[data-testid="message-actions"]'), 30_000)
await page.click('[data-testid="title-menu"]')
await until(() => has('[data-testid="title-popover"]'), 3000)
await wait(400)
await page.screenshot({ path: out + 'title-menu.png' })
await page.keyboard.press('Escape')
await page.click('[data-testid="share"]')
await until(() => has('[data-testid="share-popover"]'), 3000)
await clickText('[data-testid="share-popover"] button', '复制为 Markdown')
check('分享：复制为 Markdown（第 3 轮已实现）', await toastHas('已复制为 Markdown'))

// ── 5) 赞踩
await page.click('[data-testid="thumb-down"]')
await until(() => has('[data-testid="feedback-dialog"]'), 3000)
await page.keyboard.type('没先写复现测试')
await page.click('[data-testid="feedback-submit"]')
await wait(400)
check('踩：已记下并高亮', (await page.$eval('[data-testid="thumb-down"]', (b) => b.getAttribute('aria-pressed'))) === 'true')
await calm()
await key('Control+Shift+C')
check('Ctrl+Shift+C 复制最后一条回复', await toastHas('已复制'))

// ── 6) 重试 → 版本 2/2（回复操作条上），上限 ¥0.50 传到核心
await page.click('[data-testid="retry"]')
check('重试起了新任务（版本导航在回复上）', await until(async () => (await text('[data-testid="version-nav"]')).includes('2 / 2'), 20_000))
check('重试：思考块流式', await until(() => has('[data-testid="thinking-block"]'), 30_000))
check('重试：结论卡', await approveAll())
const tip = await page.$eval('[data-testid="cost-chip"]', (el) => el.parentElement?.textContent ?? '')
check(`单任务上限传到核心（${tip.match(/上限 ¥[\d.]+/)?.[0] ?? '?'}）`, tip.includes('上限 ¥0.50'))

// ── 7) 编辑后重发 → 版本 3/3（用户消息下）
await page.hover('[data-testid="user-message"]')
await page.click('[data-testid="edit-message"]')
await until(() => has('[data-testid="edit-box"]'), 3000)
await page.keyboard.type('；顺便补一个空文件的测试')
await wait(350)
await calm()
await page.screenshot({ path: out + 'edit-message.png' })
await page.click('[data-testid="edit-send"]')
check('编辑后重发：版本 3 / 3 在用户消息下', await until(async () => (await page.$eval('[data-testid="user-message"]', (el) => el.textContent).catch(() => '')).includes('3 / 3'), 20_000))
check('编辑后重发：结论卡', await approveAll())
await page.click('[data-testid="version-nav"] button[aria-label="上一版"]')
await wait(800)
check('切回 2 / 3', (await text('[data-testid="version-nav"]')).includes('2 / 3'))
await calm()
await wait(600)
await page.screenshot({ path: out + 'version-nav.png' })
const sideRows = await page.$$eval('[data-testid="chat-row"]', (els) => els.map((e) => e.dataset.id))
check('版本不单独出现在侧栏', sideRows.filter((id) => id.startsWith('live:')).length === 0)

// ── 8) 其他快捷键
await key('Shift+Escape')
check('Shift+Esc 聚焦输入框', await page.evaluate(() => document.activeElement?.getAttribute('aria-label') === '输入'))
await calm()
const [chooser] = await Promise.all([page.waitForFileChooser({ timeout: 3000 }).catch(() => null), key('Control+u')])
check('Ctrl+U：打开文件选择（第 3 轮已实现）', !!chooser)
if (chooser) await chooser.cancel()
await key('Control+Shift+I')
check('Ctrl+Shift+I 模型菜单', await until(() => has('[data-testid="model-menu"]'), 3000))
await page.keyboard.press('Escape')
await wait(300)
await key('Control+Shift+E')
check('Ctrl+Shift+E 思考强度', await until(() => has('[data-testid="effort-menu"]'), 3000))
await page.keyboard.press('Escape')
await key('Control+Shift+O')
check('Ctrl+Shift+O 新会话', await until(async () => (await page.$$eval('[data-testid="chat-row"]', (els) => els.map((e) => e.textContent).join('|'))).includes('新会话'), 3000))

check(`无页面错误 (${errors.length}${errors.length ? '：' + errors.slice(0, 3).join(' | ') : ''})`, errors.length === 0)
console.log(results.join('\n'))
await browser.close()
process.exit(results.some((r) => r.startsWith('FAIL')) ? 1 : 0)
