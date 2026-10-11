// 研究用：headless Chromium 性能采样（Linux 软件渲染，非 WebView2；数字只作相对参考）
// 用法：preview 在 PREVIEW_URL，dev+bridge 在 DEV_URL；node tools/perf-trace.mjs
import puppeteer from 'puppeteer-core'
const PREVIEW = process.env.PREVIEW_URL ?? 'http://localhost:1441'
const DEV = process.env.DEV_URL ?? 'http://localhost:1440'
const N = Number(process.env.TURNS ?? 12)
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const browser = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox', '--hide-scrollbars'] })
const inject = () => {
  window.__f = []; window.__lt = []
  let last = performance.now()
  const tick = (t) => { window.__f.push(t - last); last = t; requestAnimationFrame(tick) }
  requestAnimationFrame(tick)
  new PerformanceObserver((l) => l.getEntries().forEach((e) => window.__lt.push(e.duration))).observe({ type: 'longtask', buffered: true })
}
const pct = (a, p) => { const s = [...a].sort((x, y) => x - y); return s.length ? +s[Math.min(s.length - 1, Math.floor(p * s.length))].toFixed(1) : null }
const stats = (f, lt) => ({ frames: f.length, fps: +(1000 * f.length / f.reduce((a, b) => a + b, 0)).toFixed(1), p50: pct(f, .5), p95: pct(f, .95), p99: pct(f, .99), max: +Math.max(...f).toFixed(1), over33: f.filter((x) => x > 33.4).length, longTasks: lt.length, longTaskMs: Math.round(lt.reduce((a, b) => a + b, 0)), longTaskMax: Math.round(Math.max(0, ...lt)) })
const metrics = async (cdp) => { const { metrics } = await cdp.send('Performance.getMetrics'); const m = Object.fromEntries(metrics.map((x) => [x.name, x.value])); return { heapMB: +(m.JSHeapUsedSize / 1048576).toFixed(1), nodes: m.Nodes, docNodes: null, layouts: m.LayoutCount, styleRecalcs: m.RecalcStyleCount, scriptS: +m.ScriptDuration.toFixed(2), layoutS: +m.LayoutDuration.toFixed(2), styleS: +m.RecalcStyleDuration.toFixed(2) } }
const out = {}

// A) 生产构建：冷加载 + 书写推流回放 30s
{
  const page = await browser.newPage(); await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 })
  await page.evaluateOnNewDocument(inject)
  const cdp = await page.createCDPSession(); await cdp.send('Performance.enable')
  await page.goto(`${PREVIEW}/?source=fixture:success&speed=1.5`, { waitUntil: 'load' })
  const nav = await page.evaluate(() => { const n = performance.getEntriesByType('navigation')[0]; const fcp = performance.getEntriesByName('first-contentful-paint')[0]; return { dcl: Math.round(n.domContentLoadedEventEnd), load: Math.round(n.loadEventEnd), fcp: fcp ? Math.round(fcp.startTime) : null, transferKB: Math.round(performance.getEntriesByType('resource').reduce((a, r) => a + (r.transferSize || 0), n.transferSize) / 1024), fonts: performance.getEntriesByType('resource').filter((r) => r.name.endsWith('.woff2')).length } })
  const m0 = await metrics(cdp)
  await page.evaluate(() => { window.__f = []; window.__lt = [] })
  await wait(30000)
  const [f, lt] = await page.evaluate(() => [window.__f, window.__lt])
  out.A_prod_replay = { nav, at_load: m0, after30s: await metrics(cdp), domElements: await page.evaluate(() => document.getElementsByTagName('*').length), frames: stats(f, lt) }
  // 空闲 10s
  await page.evaluate(() => { window.__f = []; window.__lt = [] })
  await wait(10000)
  const [f2, lt2] = await page.evaluate(() => [window.__f, window.__lt])
  out.A_idle = { frames: stats(f2, lt2), m: await metrics(cdp) }
  await page.close()
}

// B) dev 构建 + 开发桥演示适配器：同一会话连发 N 轮，看长对话增长（TURNS=0 跳过）
if (N > 0) {
  const page = await browser.newPage(); await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 })
  await page.evaluateOnNewDocument(inject)
  const cdp = await page.createCDPSession(); await cdp.send('Performance.enable')
  await page.goto(`${DEV}/?source=fixture:success&speed=8`, { waitUntil: 'networkidle0' })
  await page.evaluate(() => localStorage.clear()); await page.reload({ waitUntil: 'networkidle0' })
  await page.evaluate(() => [...document.querySelectorAll('button')].find((b) => b.textContent?.includes('新会话'))?.click())
  await wait(500)
  out.B_turns = []
  for (let i = 0; i < N; i++) {
    await page.evaluate(() => { window.__f = []; window.__lt = [] })
    await page.click('textarea[aria-label="输入"]')
    await page.keyboard.type(`第 ${i + 1} 轮：line_count 把空行也算进去了，帮我修一下`)
    await page.keyboard.press('Enter')
    const t0 = Date.now()
    await wait(1500)
    // 等这一轮结束：发送位重新出现且无 streaming-text
    while (Date.now() - t0 < 120000) {
      const busy = await page.evaluate(() => !!document.querySelector('[data-testid="streaming-text"]') || !!document.querySelector('[data-testid="stop"]'))
      if (!busy) break
      await wait(300)
    }
    await wait(800)
    const [f, lt] = await page.evaluate(() => [window.__f, window.__lt])
    const m = await metrics(cdp)
    out.B_turns.push({ turn: i + 1, secs: Math.round((Date.now() - t0) / 1000), domElements: await page.evaluate(() => document.getElementsByTagName('*').length), heapMB: m.heapMB, frames: stats(f, lt), url: await page.evaluate(() => location.search) })
    console.error(JSON.stringify(out.B_turns.at(-1)))
  }
  await page.close()
}
console.log(JSON.stringify(out, null, 2))
await browser.close()
