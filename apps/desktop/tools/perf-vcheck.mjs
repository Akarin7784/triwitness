// 研究用：虚拟列表行为核对（300 轮压测源：流式贴底、滚到中部 / 顶部不留白、回到底部）。preview 在 :1441，截图写 /tmp/shots
import puppeteer from 'puppeteer-core'
const b = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox', '--hide-scrollbars'] })
const p = await b.newPage(); await p.setViewport({ width: 1440, height: 900 })
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
await p.goto('http://localhost:1441/?source=stress&rounds=300&speed=60', { waitUntil: 'load' })
// mid-stream: at bottom?
await wait(5000)
const mid = await p.evaluate(() => { const sc = document.querySelector('[data-testid="chat-scroll"]'); return { gap: sc.scrollHeight - sc.scrollTop - sc.clientHeight, range: document.querySelector('[data-testid="virtual-list"]')?.dataset.virtualRange, streaming: !!document.querySelector('[data-testid="streaming-text"]') } })
console.log('mid', JSON.stringify(mid))
await p.screenshot({ path: '/tmp/shots/v-mid.png' })
while (!(await p.$('[data-testid="message-actions"]'))) await wait(500)
await wait(800)
console.log('end', await p.evaluate(() => { const sc = document.querySelector('[data-testid="chat-scroll"]'); return JSON.stringify({ gap: sc.scrollHeight - sc.scrollTop - sc.clientHeight, range: document.querySelector('[data-testid="virtual-list"]')?.dataset.virtualRange }) }))
await p.screenshot({ path: '/tmp/shots/v-end.png' })
// scroll to middle
for (const frac of [0.5, 0.0]) {
  await p.evaluate((f) => { const sc = document.querySelector('[data-testid="chat-scroll"]'); sc.scrollTop = (sc.scrollHeight - sc.clientHeight) * f }, frac)
  await wait(600)
  const info = await p.evaluate(() => {
    const sc = document.querySelector('[data-testid="chat-scroll"]'); const r = sc.getBoundingClientRect()
    const vis = [...document.querySelectorAll('.v-item')].filter((e) => { const b = e.getBoundingClientRect(); return b.bottom > r.top && b.top < r.bottom }).length
    return { range: document.querySelector('[data-testid="virtual-list"]')?.dataset.virtualRange, visibleItems: vis, top: Math.round(sc.scrollTop), h: sc.scrollHeight }
  })
  console.log('frac', frac, JSON.stringify(info))
  await p.screenshot({ path: `/tmp/shots/v-${frac}.png` })
}
await p.click('[data-testid="jump-bottom"]').catch((e) => console.log('no jump btn', e.message))
await wait(1500)
console.log('after jump', await p.evaluate(() => { const sc = document.querySelector('[data-testid="chat-scroll"]'); return JSON.stringify({ gap: Math.round(sc.scrollHeight - sc.scrollTop - sc.clientHeight), jump: !!document.querySelector('[data-testid="jump-bottom"]') }) }))
await p.screenshot({ path: '/tmp/shots/v-jump.png' })
await b.close()
