// UI-21 第 3 轮：附件（选择 / 粘贴 / 拖放 / Ctrl+U）· 风格 · 项目 · 作品栏 · 分享导出 · 规则编辑器 · 沙箱检测 · 勇士横幅（mode_changed）
// 真实核心 · 演示适配器 · ¥0。用法：TW_HOME=/tmp/twhome-e2e TW_DEV_BRIDGE=1 TW_DEMO_DELAY_S=0.3 npx vite --port 1431 后
//   cd tools && URL=http://localhost:1431 node shoot-ui21c.mjs
import { readFileSync, readdirSync, existsSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import puppeteer from 'puppeteer-core'
const base = process.env.URL ?? 'http://localhost:1431'
const home = process.env.TW_HOME ?? '/tmp/twhome-e2e'
const out = new URL('../docs/', import.meta.url).pathname
const browser = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox', '--hide-scrollbars'] })
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const results = []
const check = (name, ok) => results.push(`${ok ? 'PASS' : 'FAIL'}  ${name}`)
const page = await browser.newPage()
rmSync(join(home, 'permissions.yaml'), { force: true })
rmSync(join(process.env.HOME, '.triwitness/demo/verses/.triwitness/permissions.local.yaml'), { force: true }) // 演示仓库在 ~ 下（不随 TW_HOME）
// 0.2.1 起默认“模型自动审批”（演示里是规则审核）；这里要测审批卡的“总是”，先切到询问模式
await page.evaluateOnNewDocument(() => {
  if (!localStorage.getItem('tw.prefs')) localStorage.setItem('tw.prefs', JSON.stringify({ permissionMode: 'ask' }))
})
// 记下出现过的提示（提示几秒后会消失）
await page.evaluateOnNewDocument(() => {
  window.__toasts = []
  new MutationObserver(() => {
    for (const el of document.querySelectorAll('[data-testid="toast"]')) {
      const t = el.textContent ?? ''
      if (!window.__toasts.includes(t)) window.__toasts.push(t)
    }
  }).observe(document, { childList: true, subtree: true, characterData: true })
})
await browser.defaultBrowserContext().overridePermissions(base, ['clipboard-read', 'clipboard-write', 'clipboard-sanitized-write'])
const errors = []
page.on('pageerror', (e) => errors.push(String(e)))
page.on('console', (m) => m.type() === 'error' && !m.text().includes('favicon') && errors.push(m.text()))
await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 })
const has = (sel) => page.$(sel).then(Boolean)
const count = (sel) => page.$$eval(sel, (els) => els.length)
const text = (sel) => page.$eval(sel, (el) => el.textContent?.trim() ?? '').catch(() => '')
const until = async (fn, ms = 60_000) => {
  const t0 = Date.now()
  while (Date.now() - t0 < ms) {
    if (await Promise.resolve().then(fn).catch(() => false)) return true
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
const toastHas = (t) => until(async () => (await page.evaluate(() => window.__toasts.join('|'))).includes(t), 5000)
const finish = async (scope = '允许一次', ms = 120_000) => {
  const t0 = Date.now()
  while (Date.now() - t0 < ms) {
    if (await has('[data-testid="result-card"]')) return true
    if (await has('[data-testid="approval-card"]')) await clickText('[data-testid="approval-card"] button', scope)
    await wait(300)
  }
  return false
}
const evalClick = (sel) => page.$eval(sel, (b) => b.click())
const ready = () => until(async () => (await count('[data-testid="attachment-chip"][data-status="saving"]')) === 0, 10_000)
const files = (...n) => n.map((x) => `/tmp/e2e/${x}`)

await page.goto(`${base}/?source=fixture:success&speed=20`, { waitUntil: 'networkidle0' })
await page.evaluate(() => localStorage.clear())
await page.reload({ waitUntil: 'networkidle0' })

// ── 0) 个人资料（进 guidance）
await key('Control+,')
await until(() => has('[data-testid="settings"]'), 3000)
await page.click('[data-testid="settings-nav-profile"]')
await until(() => has('#pf-name'), 3000)
await wait(300)
await page.type('#pf-name', 'Eva')
await page.type('#pf-about', '回答尽量短')
await wait(200)

// ── 1) 规则编辑器（核心 parse_rule 校验）
await page.click('[data-testid="settings-nav-permissions"]')
check('规则编辑器载入', await until(() => has('[data-testid="rules-user"]'), 20_000))
await page.type('[data-testid="new-rule"]', 'Bash(npm test')
check('坏规则：核心报语法错误', await until(async () => (await text('[data-testid="rule-validation"]')).includes('语法'), 20_000))
check('坏规则：添加键不可点', await page.$eval('[data-testid="add-rule"]', (b) => b.disabled))
await page.type('[data-testid="new-rule"]', ')')
check('好规则：✓', await until(async () => (await text('[data-testid="rule-validation"]')).includes('有效'), 20_000))
await page.click('[data-testid="add-rule"]')
check('添加后出现在“我的规则”', await until(async () => (await text('[data-testid="rules-user"]')).includes('Bash(npm test)'), 20_000))
await page.screenshot({ path: out + 'settings-rules-editor.png' })
await until(async () => (await count('[data-testid="rules-user"] [data-testid="rule-row"]')) === 1, 3000)
await evalClick('[data-testid="rules-user"] [data-testid="rule-edit"]')
await page.$eval('[data-testid="rule-edit-input"]', (el) => el.select())
await page.keyboard.type('Bash(npm run lint)')
await until(async () => !(await page.$eval('[data-testid="rule-save"]', (b) => b.disabled)), 20_000)
await page.click('[data-testid="rule-save"]')
check('编辑保存', await until(async () => (await text('[data-testid="rules-user"]')).includes('npm run lint'), 20_000))
const userYaml = () => (existsSync(join(home, 'permissions.yaml')) ? readFileSync(join(home, 'permissions.yaml'), 'utf8') : '')
if (!userYaml().includes('Bash(npm run lint)')) console.log('yaml:', userYaml())
check('写入 ~/.triwitness/permissions.yaml', userYaml().includes('Bash(npm run lint)') && !userYaml().includes('Bash(npm test)'))
await until(async () => (await count('[data-testid="rules-user"] [data-testid="rule-row"]')) === 1, 3000)
await evalClick('[data-testid="rules-user"] [data-testid="rule-delete"]')
check('删除', await until(async () => !(await text('[data-testid="rules-user"]')).includes('npm run lint'), 20_000))

// ── 2) 沙箱检测（UI-19）
await page.click('[data-testid="settings-nav-sandbox"]')
check('沙箱检测出结果', await until(async () => (await page.$eval('[data-testid="sandbox-docker"]', (el) => el.dataset.state)) !== 'unknown', 30_000))
await wait(400)
await page.screenshot({ path: out + 'settings-sandbox-detect.png' })

// ── 3) 项目：新建 · 说明 · 知识文件 · 项目里开会话
await calm()
await page.click('[data-testid="nav-projects"]')
check('项目页', await until(() => has('[data-testid="projects-page"]'), 3000))
await wait(350)
await page.screenshot({ path: out + 'projects-empty.png' })
await page.click('[data-testid="project-new"]')
await until(() => has('[data-testid="project-name"]'), 3000)
await page.type('[data-testid="project-name"]', '诗行解析')
await page.type('#pj-desc', '修 rows 解析器')
await page.click('[data-testid="project-create-save"]')
check('新建后进详情', await until(async () => (await text('[data-testid="project-title"]')) === '诗行解析', 3000))
await page.type('[data-testid="project-instructions"]', '测试一律用 unittest。')
await page.click('[data-testid="project-instr-save"]')
const kin = await page.$('[data-testid="project-file-input"]')
await kin.uploadFile(...files('conventions.txt'))
check('知识文件上传', await until(async () => (await count('[data-testid="knowledge-file"]')) === 1, 10_000))
await wait(400)
await page.screenshot({ path: out + 'project-detail.png' })
await page.click('[data-testid="project-new-chat"]')
check('项目里开新会话：输入框有项目签', await until(async () => (await text('[data-testid="project-chip"]')) === '诗行解析', 3000))

// ── 4) 风格：预设 + 自定义
await page.click('[data-testid="plus-button"]')
await until(() => has('[data-testid="plus-menu"]'), 2000)
await page.click('[data-testid="plus-style"]')
await until(() => has('[data-testid="style-menu"]'), 2000)
await wait(350)
await page.screenshot({ path: out + 'style-menu.png' })
await page.click('[data-testid="style-edit"]')
await until(() => has('[data-testid="style-dialog"]'), 2000)
await page.click('[data-testid="style-new"]')
await page.$eval('[data-testid="style-name"]', (el) => el.select())
await page.keyboard.type('诗意')
await page.type('[data-testid="style-prompt"]', '像写一首短诗那样解释')
await wait(300)
await page.screenshot({ path: out + 'style-dialog.png' })
await page.click('[data-testid="style-save"]')
check('自定义风格生效（输入框风格签）', await until(async () => (await text('[data-testid="style-chip"]')).includes('诗意'), 3000))

// ── 5) 附件：选择 · 粘贴 · 拖放 · Ctrl+U · 预览 · 移除
const fin = await page.$('[data-testid="file-input"]')
await fin.uploadFile(...files('notes.md', 'shot.png'))
await ready()
check('选择文件 → 两个附件签', (await count('[data-testid="attachment-chip"][data-status="ready"]')) === 2)
check('图片提示：模型只读文字', await has('[data-testid="image-note"]'))
await page.evaluate(() => {
  const dt = new DataTransfer()
  dt.items.add(new File(['pasted text 粘贴'], 'clip.txt', { type: 'text/plain' }))
  const ta = document.querySelector('[data-testid="composer"] textarea')
  ta.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true }))
})
await ready()
check('粘贴文件', (await count('[data-testid="attachment-chip"]')) === 3)
await page.evaluate(() => {
  const dt = new DataTransfer()
  dt.items.add(new File(['dropped'], 'drop.log', { type: 'text/plain' }))
  const sec = document.querySelector('[data-testid="composer"]').closest('section')
  sec.dispatchEvent(new DragEvent('dragenter', { dataTransfer: dt, bubbles: true, cancelable: true }))
})
check('拖入时出现放置层', await until(() => has('[data-testid="drop-overlay"]'), 2000))
await wait(300)
await page.screenshot({ path: out + 'drop-overlay.png' })
await page.evaluate(() => {
  const dt = new DataTransfer()
  dt.items.add(new File(['dropped'], 'drop.log', { type: 'text/plain' }))
  const sec = document.querySelector('[data-testid="composer"]').closest('section')
  sec.dispatchEvent(new DragEvent('drop', { dataTransfer: dt, bubbles: true, cancelable: true }))
})
await ready()
check('拖放文件', (await count('[data-testid="attachment-chip"]')) === 4 && !(await has('[data-testid="drop-overlay"]')))
const [chooser] = await Promise.all([page.waitForFileChooser({ timeout: 3000 }).catch(() => null), (async () => (await calm(), key('Control+u')))()])
check('Ctrl+U 打开文件选择', !!chooser)
if (chooser) await chooser.cancel()
await evalClick('[data-testid="attachment-chip"]')
check('附件预览', await until(() => has('[data-testid="attachment-preview"]'), 2000))
await wait(350)
await page.keyboard.press('Escape')
await until(async () => !(await has('[data-testid="attachment-preview"]')), 2000)
const removeLast = () => page.$$eval('[data-testid="attachment-remove"]', (b) => b[b.length - 1].click())
await removeLast()
await until(async () => (await count('[data-testid="attachment-chip"]')) === 3, 3000)
await removeLast()
check('移除附件', await until(async () => (await count('[data-testid="attachment-chip"]')) === 2, 3000))
await wait(400)
await page.screenshot({ path: out + 'composer-attachments.png' })

// 发送 → 核心收到附件 + 用户设置；审批卡选“总是” → 写入仓库规则
await page.type('[data-testid="composer"] textarea', '修复 parse_rows 遇到空行崩溃')
await page.click('[data-testid="send"]')
check('任务完成（总是允许）', await finish('总是'))
check('“总是”提示写入规则', await toastHas('已写入此仓库规则'))
check('发送后用户消息带附件签', (await text('[data-testid="sent-attachments"]')).includes('notes.md'))
const runs = readdirSync(join(home, 'runs')).filter((d) => d.startsWith('r_')).sort()
const lastRun = join(home, 'runs', runs[runs.length - 1])
const archived = existsSync(join(lastRun, 'attachments')) ? readdirSync(join(lastRun, 'attachments')).sort() : []
check('核心留档附件（含项目知识文件）', ['conventions.txt', 'notes.md', 'shot.png'].every((n) => archived.includes(n)))
const gdir = join(home, 'attachments', 'guidance')
const guide = existsSync(gdir) ? readdirSync(gdir).map((f) => readFileSync(join(gdir, f), 'utf8')).join('\n') : ''
check('用户设置交给核心：称呼 / 风格 / 项目说明', guide.includes('称呼：Eva') && guide.includes('诗意') && guide.includes('测试一律用 unittest'))
check('侧栏按项目分组', await until(async () => (await text('[data-testid="project-group"]')).includes('诗行解析'), 3000))

// ── 6) 作品栏
check('作品卡（pr.md / patch.diff）', await until(async () => (await count('[data-testid="artifact-card"]')) >= 2, 10_000))
await clickText('[data-testid="artifact-card"]', 'patch.diff')
check('作品栏打开', await until(() => has('[data-testid="artifact-panel"]'), 3000))
await wait(700)
await calm()
await page.screenshot({ path: out + 'artifact-diff.png' })
const w0 = await page.$eval('[data-testid="artifact-panel"]', (el) => el.getBoundingClientRect().width)
const h = await page.$('[data-testid="artifact-resize"]')
const hb = await h.boundingBox()
await page.mouse.move(hb.x + 2, hb.y + 300)
await page.mouse.down()
await page.mouse.move(hb.x - 120, hb.y + 300, { steps: 8 })
await page.mouse.up()
await wait(300)
const w1 = await page.$eval('[data-testid="artifact-panel"]', (el) => el.getBoundingClientRect().width)
check('拖动调宽', w1 > w0 + 80)
check('宽度记住', (await page.evaluate(() => JSON.parse(localStorage.getItem('tw.prefs')).artifactWidth)) === Math.round(w1))
await page.click('[data-testid="artifact-download"]')
check('下载（浏览器预览走普通下载）', await toastHas('已下载'))
await clickText('[data-testid="artifact-card"]', 'pr.md')
await wait(500)
check('切到 pr.md（Markdown 渲染）', (await text('[data-testid="artifact-title"]')) === 'pr.md' && (await has('[data-testid="artifact-body"] .md')))
await page.screenshot({ path: out + 'artifact-markdown.png' })
await calm()
await page.keyboard.press('Escape')
check('Esc 关闭作品栏', await until(async () => !(await has('[data-testid="artifact-panel"]')), 3000))

// ── 7) 分享 / 导出（只在本机）
await page.click('[data-testid="share"]')
await until(() => has('[data-testid="share-popover"]'), 2000)
await wait(300)
await page.screenshot({ path: out + 'share-local.png' })
check('分享说明只在本机', (await text('[data-testid="share-popover"]')).includes('只在本机'))
await page.click('[data-testid="share-copy"]')
await toastHas('已复制为 Markdown')
const md = await page.evaluate(() => navigator.clipboard.readText())
check('复制为 Markdown：含标题 / 你 / 结论 / 附件', md.startsWith('# ') && md.includes('## 你') && md.includes('## 结论') && md.includes('notes.md'))
await page.click('[data-testid="share"]')
await until(() => has('[data-testid="share-popover"]'), 2000)
await page.click('[data-testid="share-md"]')
check('导出 Markdown', await toastHas('已下载'))
await page.click('[data-testid="share"]')
await until(() => has('[data-testid="share-popover"]'), 2000)
await page.evaluate(() => (window.__printed = 0))
await page.click('[data-testid="share-pdf"]')
check('导出 PDF：生成打印文档', await until(() => page.evaluate(() => [...document.querySelectorAll('iframe')].some((f) => f.contentDocument?.title && f.contentDocument.body.innerHTML.includes('<h1>'))), 3000))

// ── 8) 作品页
await page.click('[data-testid="nav-artifacts"]')
check('作品页列出产出', await until(async () => (await count('[data-testid="artifact-entry"]')) >= 2, 3000))
await wait(400)
await page.screenshot({ path: out + 'artifacts-page.png' })
await page.click('[data-testid="artifact-entry"]')
check('从作品页打开 → 会话 + 作品栏', await until(() => has('[data-testid="artifact-panel"]'), 3000))
await page.click('[data-testid="artifact-close"]')

// ── 9) “总是”写进了仓库规则（设置里看得到）
await key('Control+,')
await page.click('[data-testid="settings-nav-permissions"]')
check('此仓库规则里有“总是”写入的那条', await until(async () => (await text('[data-testid="rules-local"]')).includes('submit_repro') || (await count('[data-testid="rules-local"] [data-testid="rule-row"]')) > 0, 20_000))

// ── 10) 勇士模式横幅（核心 mode_changed 驱动）
await page.click('[data-testid="perm-full_access"]')
await until(() => has('[data-testid="unrestricted-dialog"]'), 3000)
await page.click('[data-testid="unrestricted-ack"]')
await page.type('[data-testid="unrestricted-phrase"]', '我了解风险')
await page.click('[data-testid="unrestricted-arm"]')
await wait(300)
await calm()
await key('Control+Shift+O')
await until(() => has('[data-testid="composer"] textarea'), 3000)
await page.type('[data-testid="composer"] textarea', '勇士模式下修复空行')
await page.click('[data-testid="send"]')
check('核心报 risk=high → 红色横幅', await until(() => has('[data-testid="unrestricted-banner"]'), 30_000))
await wait(500)
await page.screenshot({ path: out + 'unrestricted-banner-live.png' })
check('勇士模式下没有审批卡', (await finish('允许一次')) && !(await has('[data-testid="approval-card"]')))
check('任务结束自动回退 → 横幅消失', await until(async () => !(await has('[data-testid="unrestricted-banner"]')), 10_000))

check('无页面错误', errors.length === 0)
console.log(results.join('\n'))
if (errors.length) console.log(errors.join('\n'))
await browser.close()
process.exit(results.some((r) => r.startsWith('FAIL')) ? 1 : 0)
