// UI 全面审查（2026-10-11）：浅色 / 深色每个页面和状态截图 + 自动检查
//   溢出 / 出界、文字对比度、键盘焦点可见、中文字体与行高、动画帧间隔（卡顿）、减少动态效果
// 真实核心 · 演示适配器 · ¥0。用法：TW_DEV_BRIDGE=1 TW_DEMO_DELAY_S=0.3 npx vite --port 1431 后
//   cd tools && URL=http://localhost:1431 node shoot-review.mjs [light|dark|en|motion ...]
import { mkdirSync, writeFileSync } from 'node:fs'
import puppeteer from 'puppeteer-core'
const base = process.env.URL ?? 'http://localhost:1431'
const out = new URL('../docs/review/', import.meta.url).pathname
mkdirSync(out, { recursive: true })
const passes = process.argv.slice(2).length ? process.argv.slice(2) : ['light', 'dark', 'en', 'motion']
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const report = { shots: [], audits: {}, frames: {}, motion: {}, typography: {}, errors: [] }

// ── 页面内审计（在浏览器里跑）
function auditInPage() {
  const vis = (el) => {
    const r = el.getBoundingClientRect()
    if (r.width < 1 || r.height < 1) return false
    for (let e = el; e; e = e.parentElement) {
      const cs = getComputedStyle(e)
      if (cs.visibility === 'hidden' || cs.display === 'none' || Number(cs.opacity) < 0.05) return false
    }
    return true
  }
  const name = (el) => {
    const id = el.closest('[data-testid]')?.getAttribute('data-testid')
    return `${el.tagName.toLowerCase()}${id ? `@${id}` : ''}「${(el.textContent ?? '').trim().slice(0, 24)}」`
  }
  const parse = (c) => {
    const m = c.match(/rgba?\(([^)]+)\)/)
    if (!m) return null
    const [r, g, b, a = 1] = m[1].split(/[ ,/]+/).filter(Boolean).map(Number)
    return { r, g, b, a }
  }
  const lum = ({ r, g, b }) => {
    const f = (v) => ((v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
  }
  const blend = (top, bottom) => ({ r: top.r * top.a + bottom.r * (1 - top.a), g: top.g * top.a + bottom.g * (1 - top.a), b: top.b * top.a + bottom.b * (1 - top.a), a: 1 })
  const bgOf = (el) => {
    const layers = []
    for (let e = el; e; e = e.parentElement) {
      const c = parse(getComputedStyle(e).backgroundColor)
      if (c && c.a > 0) {
        layers.push(c)
        if (c.a >= 1) break
      }
    }
    let acc = { r: 255, g: 255, b: 255, a: 1 }
    for (const l of layers.reverse()) acc = blend(l, acc)
    return acc
  }
  const overflow = []
  const offscreen = []
  const contrast = []
  for (const el of document.querySelectorAll('body *')) {
    if (!vis(el)) continue
    const cs = getComputedStyle(el)
    const r = el.getBoundingClientRect()
    if (cs.position !== 'fixed' && (r.right > innerWidth + 1 || r.bottom > innerHeight + 400) && !el.closest('[data-allow-offscreen]')) {
      // 只记录真正露在可视区外、且没有被祖先裁剪的
      let clipped = false
      for (let e = el.parentElement; e; e = e.parentElement) {
        const ps = getComputedStyle(e)
        if (/(hidden|auto|scroll|clip)/.test(ps.overflowX + ps.overflowY)) {
          clipped = true
          break
        }
      }
      if (!clipped && r.right > innerWidth + 1) offscreen.push(name(el))
    }
    const ownText = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())
    if (ownText && cs.overflowX === 'visible' && el.scrollWidth > el.clientWidth + 2 && cs.display !== 'inline' && cs.whiteSpace === 'nowrap') overflow.push(name(el))
    if (ownText && (el.textContent ?? '').trim().length > 1 && !el.closest('.writing-char, [data-streaming]') && !el.closest('[disabled],[aria-disabled="true"]') && !el.closest('.tip') && !['TEXTAREA', 'INPUT', 'OPTION'].includes(el.tagName)) {
      const fg = parse(cs.color)
      if (!fg) continue
      let op = 1
      for (let e = el; e; e = e.parentElement) op *= Number(getComputedStyle(e).opacity)
      const bg = bgOf(el)
      const f = blend({ ...fg, a: fg.a * op }, bg)
      const L1 = lum(f)
      const L2 = lum(bg)
      const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05)
      const size = parseFloat(cs.fontSize)
      const need = size >= 18.66 || (size >= 14 && Number(cs.fontWeight) >= 700) ? 3 : 4.5
      if (ratio < need) contrast.push(`${name(el)} ${ratio.toFixed(2)}<${need} (${size}px)`)
    }
  }
  return { overflow: [...new Set(overflow)], offscreen: [...new Set(offscreen)], contrast: [...new Set(contrast)] }
}

function typographyInPage() {
  const pick = (sel) => {
    const el = document.querySelector(sel)
    if (!el) return null
    const cs = getComputedStyle(el)
    return { font: cs.fontFamily.split(',')[0], size: cs.fontSize, lineHeight: (parseFloat(cs.lineHeight) / parseFloat(cs.fontSize)).toFixed(2), letterSpacing: cs.letterSpacing }
  }
  return {
    fontsReady: document.fonts.status,
    serifSC: document.fonts.check('16px "Noto Serif SC"', '中'),
    sansSC: document.fonts.check('16px "Noto Sans SC"', '中'),
    message: pick('article .selectable, .md p'),
    composer: pick('[data-testid="composer"] textarea'),
    sidebarRow: pick('[data-testid="chat-row"]'),
    lang: document.documentElement.lang,
  }
}

async function run(passName) {
  const theme = passName === 'dark' ? 'dark' : 'light'
  const language = passName === 'en' ? 'en' : 'zh'
  const browser = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox', '--hide-scrollbars'] })
  const ctx = browser.defaultBrowserContext()
  await ctx.overridePermissions(base, ['clipboard-read', 'clipboard-write', 'clipboard-sanitized-write'])
  const page = await browser.newPage()
  page.on('pageerror', (e) => report.errors.push(`${passName}: ${e}`))
  page.on('console', (m) => m.type() === 'error' && !m.text().includes('favicon') && report.errors.push(`${passName}: ${m.text()}`))
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 })
  if (passName === 'motion') await page.emulateMediaFeatures([{ name: 'prefers-reduced-motion', value: 'reduce' }])
  await page.evaluateOnNewDocument(
    (theme, language) => {
      if (!localStorage.getItem('tw.review.seeded')) {
        localStorage.setItem('tw.prefs', JSON.stringify({ theme, language, name: 'Eva' }))
        localStorage.setItem('tw.review.seeded', '1')
      }
    },
    theme,
    language,
  )
  const has = (sel) => page.$(sel).then(Boolean)
  const until = async (fn, ms = 60_000) => {
    const t0 = Date.now()
    while (Date.now() - t0 < ms) {
      if (await Promise.resolve().then(fn).catch(() => false)) return true
      await wait(150)
    }
    return false
  }
  const key = async (combo) => {
    const parts = combo.split('+')
    const last = parts.pop()
    for (const p of parts) await page.keyboard.down(p)
    await page.keyboard.press(last)
    for (const p of parts.reverse()) await page.keyboard.up(p)
  }
  const calm = async () => {
    await page.mouse.move(1430, 450)
    await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur())
  }
  const clickText = (sel, t) =>
    page.evaluate((sel, t) => {
      const el = [...document.querySelectorAll(sel)].find((b) => b.textContent?.includes(t))
      el?.click()
      return !!el
    }, sel, t)
  const audits = (report.audits[passName] = {})
  const shot = async (id, { audit = true } = {}) => {
    await wait(450)
    const file = `${passName}-${id}.jpg`
    await page.screenshot({ path: out + file, type: 'jpeg', quality: 82 })
    console.error('shot', file, new Date().toISOString().slice(11, 19))
    report.shots.push(file)
    if (audit && passName !== 'motion') audits[id] = await page.evaluate(auditInPage)
  }
  // 帧间隔：动作期间记录 rAF
  const frames = async (id, action) => {
    await page.evaluate(() => {
      window.__f = []
      let last = performance.now()
      const tick = (t) => {
        window.__f.push(t - last)
        last = t
        if (window.__f.length < 400 && !window.__stop) requestAnimationFrame(tick)
      }
      window.__stop = false
      requestAnimationFrame(tick)
    })
    await action()
    await wait(700)
    const d = await page.evaluate(() => ((window.__stop = true), window.__f.slice(1)))
    const s = [...d].sort((a, b) => a - b)
    report.frames[`${passName}:${id}`] = { n: d.length, p50: +s[Math.floor(s.length * 0.5)]?.toFixed(1), p95: +s[Math.floor(s.length * 0.95)]?.toFixed(1), max: +Math.max(...d).toFixed(1), over33: d.filter((x) => x > 33.4).length }
  }

  await page.goto(`${base}/?source=fixture:success&speed=20`, { waitUntil: 'networkidle0' })
  await until(() => has('[data-testid="composer"]'), 10_000)
  await calm()
  await shot('00-fixture-chat')
  await page.click('[data-testid="nav-new"]')
  await wait(400)
  await calm()
  await shot('01-home')
  if (passName === 'light' || passName === 'en') report.typography[passName] = await page.evaluate(typographyInPage)

  // 键盘焦点：从页面开头按 Tab，看每个焦点有没有可见指示
  if (passName === 'light' || passName === 'dark') {
    const noRing = []
    await page.evaluate(() => document.body.focus())
    for (let i = 0; i < 28; i++) {
      await page.keyboard.press('Tab')
      const f = await page.evaluate(() => {
        const el = document.activeElement
        if (!el || el === document.body) return null
        const cs = getComputedStyle(el)
        const ring = (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0) || (cs.boxShadow && cs.boxShadow !== 'none')
        const label = el.getAttribute('aria-label') || el.getAttribute('data-testid') || (el.textContent ?? '').trim().slice(0, 16) || el.tagName
        return { ring, label }
      })
      if (f && !f.ring) noRing.push(f.label)
    }
    report.audits[`${passName}:focus-without-ring`] = [...new Set(noRing)]
    await page.keyboard.press('Tab')
    await shot('02-focus-ring', { audit: false })
    await calm()
  }

  // 菜单
  await frames('plus-menu', async () => {
    await page.click('[data-testid="plus-button"]')
  })
  await shot('03-plus-menu')
  await page.keyboard.press('Escape')
  await calm()
  await page.click('[data-testid="model-picker"]').catch(() => {})
  await shot('04-model-menu')
  await page.keyboard.press('Escape')
  await calm()

  // 跑一个演示任务：审批卡 → 结果
  await page.type('[data-testid="composer"] textarea', language === 'en' ? 'line_count counts blank lines' : 'line_count 把空行也算进去了')
  await frames('streaming', async () => {
    await page.click('[data-testid="send"]')
    await wait(1500)
  })
  if (await until(() => has('[data-testid="approval-card"]'), 60_000)) {
    await calm()
    await shot('05-approval')
  }
  const t0 = Date.now()
  while (Date.now() - t0 < 120_000) {
    if (await has('[data-testid="result-card"]')) break
    if (await has('[data-testid="approval-card"]')) await clickText('[data-testid="approval-card"] button', language === 'en' ? 'Allow once' : '允许一次')
    await wait(300)
  }
  await calm()
  await shot('06-chat-result')
  await page.evaluate(() => document.querySelector('main [data-scroll], main .overflow-y-auto')?.scrollTo({ top: 0 }))
  await shot('07-chat-top')
  if (passName === 'motion') {
    // 减少动态效果：菜单出现应几乎瞬时；CSS 动画应被关掉
    const t1 = await page.evaluate(async () => {
      const t = performance.now()
      document.querySelector('[data-testid="plus-button"]').click()
      return new Promise((res) => {
        const check = () => {
          const m = document.querySelector('[data-testid="plus-menu"]')
          if (m && getComputedStyle(m).opacity === '1' && ['none', 'matrix(1, 0, 0, 1, 0, 0)'].includes(getComputedStyle(m).transform)) res(performance.now() - t)
          else if (performance.now() - t > 2000) res(-1)
          else requestAnimationFrame(check)
        }
        check()
      })
    })
    report.motion.plusMenuSettleMs = Math.round(t1)
    await page.keyboard.press('Escape')
    report.motion.cssAnimations = await page.evaluate(() => {
      const out = {}
      for (const sel of ['.fade-in', '.indeterminate', '.animate-spin', '.caret, .cursor']) {
        const el = document.querySelector(sel)
        if (el) out[sel] = getComputedStyle(el).animationDuration + ' ' + getComputedStyle(el).animationName
      }
      return out
    })
  }

  // 作品栏
  if (await has('[data-testid="artifact-card"]')) {
    await frames('artifact-open', async () => {
      await page.evaluate(() => document.querySelector('[data-testid="artifact-card"]').click())
    })
    await until(() => has('[data-testid="artifact-panel"]'), 3000)
    await calm()
    await shot('08-artifact-diff')
    await clickText('[data-testid="artifact-card"]', 'pr.md')
    await shot('09-artifact-markdown')
    await page.keyboard.press('Escape')
    await wait(400)
  }
  // 标题菜单 / 分享
  await page.click('[data-testid="title-menu"]').catch(() => {})
  await shot('10-title-menu')
  await page.keyboard.press('Escape')
  await page.click('[data-testid="share"]').catch(() => {})
  await shot('11-share')
  await page.keyboard.press('Escape')
  await calm()
  // 搜索 / 快捷键
  await key('Control+k')
  await shot('12-search')
  await page.keyboard.press('Escape')
  await key('Control+/')
  await shot('13-shortcuts')
  await page.keyboard.press('Escape')
  // 侧栏收起
  await calm()
  await frames('sidebar-collapse', () => key('Control+Shift+S'))
  await shot('14-sidebar-collapsed')
  await key('Control+Shift+S')
  await wait(400)
  // 会话菜单 / 删除确认
  await page.hover('[data-testid="chat-row"]').catch(() => {})
  await page.evaluate(() => document.querySelector('[data-testid="chat-row"] [aria-label="更多"], [data-testid="chat-row"] [aria-label="More"]')?.click())
  await shot('15-chat-menu')
  await page.keyboard.press('Escape')
  await calm()
  // 风格对话框
  await page.click('[data-testid="plus-button"]')
  await page.click('[data-testid="plus-style"]').catch(() => {})
  await wait(250)
  await shot('16-style-menu')
  await page.evaluate(() => document.querySelector('[data-testid="style-edit"]')?.click())
  await until(() => has('[data-testid="style-dialog"]'), 2000)
  await shot('17-style-dialog')
  await page.keyboard.press('Escape')
  await wait(400)
  await calm()
  // 项目
  await page.click('[data-testid="nav-projects"]')
  await until(() => has('[data-testid="projects-page"]'), 3000)
  await shot('18-projects-empty')
  await page.click('[data-testid="project-new"]')
  await until(() => has('[data-testid="project-name"]'), 2000)
  await page.type('[data-testid="project-name"]', language === 'en' ? 'Poetry tools' : '诗集工具')
  await shot('19-project-create')
  await page.click('[data-testid="project-create-save"]')
  await wait(500)
  await shot('20-project-detail')
  // 作品页
  await page.click('[data-testid="nav-artifacts"]')
  await shot('21-artifacts-page')
  // 设置各分区
  await calm()
  await key('Control+,')
  await until(() => has('[data-testid="settings"]'), 3000)
  for (const [i, s] of ['general', 'profile', 'model', 'budget', 'permissions', 'sandbox', 'connectors', 'privacy', 'about'].entries()) {
    if (i === 1) await frames('settings-switch', () => page.click(`[data-testid="settings-nav-${s}"]`))
    else await page.click(`[data-testid="settings-nav-${s}"]`)
    await wait(350)
    await shot(`3${i}-settings-${s}`)
    // 长分区：滚到底再拍一张
    const scrolled = await page.evaluate(() => {
      const el = [...document.querySelectorAll('[data-testid="settings"] *')].find((e) => /(auto|scroll)/.test(getComputedStyle(e).overflowY) && e.scrollHeight > e.clientHeight + 40)
      if (!el) return false
      el.scrollTop = el.scrollHeight
      return true
    })
    if (scrolled) await shot(`3${i}-settings-${s}-bottom`)
  }
  await page.click('[data-testid="settings-nav-permissions"]')
  await wait(300)
  await page.evaluate(() => document.querySelector('[data-testid="perm-unrestricted"]')?.click())
  if (await until(() => has('[data-testid="unrestricted-dialog"]'), 2000)) await shot('40-unrestricted-dialog')
  await page.keyboard.press('Escape')
  await page.click('[data-testid="settings-nav-about"]')
  await page.evaluate(() => document.querySelector('[data-testid="open-licenses"]')?.click())
  if (await until(() => has('[data-testid="licenses-dialog"]'), 2000)) await shot('41-licenses')
  await page.keyboard.press('Escape')
  await page.click('[data-testid="settings-nav-privacy"]')
  await page.evaluate(() => document.querySelector('[data-testid="clear-history"]')?.click())
  if (await until(() => has('[data-testid="clear-dialog"]'), 2000)) await shot('42-clear-dialog')
  await page.keyboard.press('Escape')
  // 窄窗口：960×640
  await page.keyboard.press('Escape')
  await page.setViewport({ width: 960, height: 640, deviceScaleFactor: 1 })
  await page.click('[data-testid="nav-new"]').catch(() => {})
  await calm()
  await shot('50-narrow-home')
  await page.evaluate(() => document.querySelector('[data-testid="chat-row"]')?.click())
  await wait(500)
  await shot('51-narrow-chat')
  await browser.close()
}

for (const p of passes) {
  try {
    await run(p)
  } catch (e) {
    report.errors.push(`${p}: script ${e?.stack ?? e}`)
  }
}
writeFileSync('/tmp/review-report.json', JSON.stringify(report, null, 2))
const sum = (k) => Object.entries(report.audits).filter(([n]) => !n.includes(':')).flatMap(([p, a]) => Object.entries(a).flatMap(([id, r]) => r[k].map((x) => `${p}/${id}: ${x}`)))
console.log('shots', report.shots.length)
for (const k of ['overflow', 'offscreen', 'contrast']) console.log(`\n## ${k} (${sum(k).length})\n` + sum(k).slice(0, 80).join('\n'))
console.log('\n## focus', JSON.stringify(Object.fromEntries(Object.entries(report.audits).filter(([n]) => n.includes(':')))))
console.log('\n## frames', JSON.stringify(report.frames, null, 1))
console.log('\n## motion', JSON.stringify(report.motion))
console.log('\n## typography', JSON.stringify(report.typography, null, 1))
console.log('\n## errors', report.errors.join('\n'))
