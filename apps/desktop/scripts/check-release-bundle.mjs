/**
 * 0.3.1：正式版前端包里不能有演示 / 回放 / 压测来源（只在 import.meta.env.DEV 下）。
 * `npm run build` 之后运行：扫 dist/ 下全部文件，命中任何标记就失败。
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const DIST = fileURLToPath(new URL('../dist/', import.meta.url))
const MARKERS = [
  '演示', // 「演示」选项 / 签 / 文案
  'demo/verses', // 演示仓库
  '--demo',
  '床前明月光', // 演示脚本内容
  'tw.core.mode', // 运行方式设置
  'fixtures/events', // 录好的轨迹回放
  '"tw_events_fixture"',
  'stress-', // 压测源
  'Issue #87 · 演示',
]

const files = []
const walk = (d) => {
  for (const n of readdirSync(d)) {
    const p = join(d, n)
    if (statSync(p).isDirectory()) walk(p)
    else files.push(p)
  }
}
walk(DIST)
const jsonl = files.filter((f) => f.endsWith('.jsonl') || /[\\/](success|failure|budget_exceeded|recorded)-[\w-]+\.js$/.test(f))
const hits = []
for (const f of files) {
  if (!/\.(js|css|html|json|jsonl|txt|map)$/.test(f)) continue
  const text = readFileSync(f, 'utf8')
  for (const m of MARKERS) if (text.includes(m)) hits.push(`${f.slice(DIST.length)}: ${m}`)
}
if (hits.length || jsonl.length) {
  console.error('正式版前端包混入了开发 / 演示内容：')
  for (const h of [...hits, ...jsonl]) console.error('  ' + h)
  process.exit(1)
}
console.log(`release bundle 检查通过：${files.length} 个文件，未含演示 / 回放 / 压测来源`)
