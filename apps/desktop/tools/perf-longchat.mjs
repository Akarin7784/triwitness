// 研究用：长回合压测（headless Chrome，Linux 软件渲染，非 WebView2——只看相对值）
// MODE=stress（默认）：生产构建 + ?source=stress&rounds=N，经真实 React 渲染路径把一个超长回合流式推完，
//   记录推流期帧时 / long task / 完成用时，完成后测 DOM 规模、JS 堆、整页重排、流式追加重排、滚动帧时。
// （早先的“克隆 DOM K 份”代理实验结果保留在 docs/research/native-vs-web-ui.md §3.4。）
// 用法：npm run build && npx vite preview --port 1441 后  node tools/perf-longchat.mjs
import puppeteer from 'puppeteer-core'
const PREVIEW = process.env.PREVIEW_URL ?? 'http://localhost:1441'
// CASES：rounds 或 rounds x repeat（如 1x150 = 一条超长回答）
const CASES = (process.env.CASES ?? '200,500,1x150').split(',').map((c) => c.split('x').map(Number))
const SPEED = process.env.SPEED ?? '40'
const LIMIT = Number(process.env.LIMIT_S ?? 240) * 1000
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const browser = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox', '--hide-scrollbars'] })
const pct = (a, p) => { const s = [...a].sort((x, y) => x - y); return s.length ? +s[Math.min(s.length - 1, Math.floor(p * s.length))].toFixed(1) : null }
const inject = () => {
  window.__f = []; window.__lt = []
  let last = performance.now()
  const tick = (t) => { window.__f.push(t - last); last = t; requestAnimationFrame(tick) }
  requestAnimationFrame(tick)
  new PerformanceObserver((l) => l.getEntries().forEach((e) => window.__lt.push(e.duration))).observe({ type: 'longtask', buffered: true })
}
const res = []
for (const [rounds, repeat = 1] of CASES) {
  const page = await browser.newPage(); await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 })
  await page.evaluateOnNewDocument(inject)
  const cdp = await page.createCDPSession(); await cdp.send('Performance.enable')
  await page.goto(`${PREVIEW}/?source=stress&rounds=${rounds}&repeat=${repeat}&speed=${SPEED}`, { waitUntil: 'load' })
  await page.evaluate(() => localStorage.clear())
  await page.reload({ waitUntil: 'load' })
  const t0 = Date.now()
  let done = false
  while (Date.now() - t0 < LIMIT) {
    done = await page.evaluate(() => !!document.querySelector('[data-testid="message-actions"]')).catch(() => false)
    if (done) break
    await wait(500)
  }
  const loadS = +((Date.now() - t0) / 1000).toFixed(1)
  const [f, lt] = await page.evaluate(() => [window.__f, window.__lt])
  await wait(1500)
  await cdp.send('HeapProfiler.collectGarbage').catch(() => {})
  const { metrics } = await cdp.send('Performance.getMetrics'); const m = Object.fromEntries(metrics.map((x) => [x.name, x.value]))
  const r = await page.evaluate(async () => {
    const sc = document.querySelector('[data-testid="chat-scroll"]')
    const t1 = performance.now(); sc.style.width = '90%'; void sc.offsetHeight; const reflow = performance.now() - t1
    sc.style.width = ''; void sc.offsetHeight
    const host = document.querySelector('[data-testid="assistant-turn"]') ?? sc.firstElementChild
    const p = document.createElement('p'); host.appendChild(p)
    const t2 = performance.now(); p.textContent = '新写出的一段字。'.repeat(8); void sc.scrollHeight; const append = performance.now() - t2
    p.remove()
    sc.scrollTop = sc.scrollHeight
    await new Promise((r) => setTimeout(r, 300))
    const fr = []; let last = performance.now()
    await new Promise((ok) => { const end = last + 2000; const tick = (t) => { fr.push(t - last); last = t; sc.scrollTop -= 40; if (t < end) requestAnimationFrame(tick); else ok() }; requestAnimationFrame(tick) })
    fr.sort((a, b) => a - b)
    return {
      blocks: document.querySelectorAll('[data-testid="tool-row"]').length,
      domElements: document.getElementsByTagName('*').length,
      reflowMs: +reflow.toFixed(1), appendMs: +append.toFixed(1),
      scrollP50: +fr[Math.floor(fr.length * .5)].toFixed(1), scrollP95: +fr[Math.floor(fr.length * .95)].toFixed(1), scrollMax: +fr.at(-1).toFixed(1),
      scrollFps: +(1000 * fr.length / fr.reduce((a, b) => a + b, 0)).toFixed(1),
    }
  })
  const row = {
    rounds, repeat, finished: done, loadS,
    stream: { fps: +(1000 * f.length / f.reduce((a, b) => a + b, 0)).toFixed(1), p50: pct(f, .5), p95: pct(f, .95), p99: pct(f, .99), over33: f.filter((x) => x > 33.4).length, longTasks: lt.length, longTaskMs: Math.round(lt.reduce((a, b) => a + b, 0)), longTaskMax: Math.round(Math.max(0, ...lt)) },
    heapMB: +(m.JSHeapUsedSize / 1048576).toFixed(1), nodes: m.Nodes, ...r,
  }
  res.push(row); console.error(JSON.stringify(row))
  await page.close()
}
console.log(JSON.stringify(res, null, 2))
await browser.close()
