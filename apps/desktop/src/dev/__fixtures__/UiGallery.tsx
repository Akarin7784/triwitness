/**
 * 仅开发版：UI 走查样例页（tw-ui-gallery）。入口 ?gallery=1，只在 import.meta.env.DEV 下动态加载；
 * 正式版不打包（check-release-bundle 扫描标记 tw-ui-gallery）。
 */
import { useEffect, useState } from 'react'
import { ApprovalCard } from '../../components/ApprovalCard'
import { ResultCard } from '../../components/ResultCard'
import { Markdown } from '../../components/Markdown'
import { StreamingText } from '../../components/StreamingText'
import { ApiKeyDialog } from '../../components/ApiKeyDialog'
import type { ResultMsg } from '../../bridge/protocol'
import type { PendingApproval } from '../../bridge/liveTask'
import { getPrefs } from '../../lib/prefs'

const MD = `# 一级标题：修复登录超时

\`\`\`python
# 刷新 token：并发时复用同一个请求
async def refresh(self, key: str) -> Token:
    async with self._lock:
        if (t := self._cache.get(key)) and not t.expired:
            return t
        return await self._fetch("POST", timeout=30)
\`\`\`

\`\`\`diff
- return len(text.split("\\n"))
+ return sum(1 for line in text.splitlines() if line.strip())
\`\`\`

## 二级标题
### 三级标题

正文段落，测试 16px / 1.7 行高与约 68 字行宽。这里是一段较长的中文说明，用来观察换行、标点与段距在长时间阅读下是否舒适。行内代码 \`retry_after\` 与[链接](https://example.com)。

> 引用：先复现，再修复，最后复验。

- 列表项一
- 列表项二
  1. 嵌套有序

\`\`\`ts
// 代码块：降饱和高亮
export async function login(user: string, timeoutMs = 3000): Promise<boolean> {
  const res = await fetch('/api/login', { method: 'POST', body: JSON.stringify({ user }) })
  return res.ok && timeoutMs > 0
}
\`\`\`

| 文件 | 增 | 删 |
|---|---:|---:|
| src/auth/login.ts | 18 | 4 |
| tests/test_login.py | 32 | 0 |

---

结尾段落。`

const APPROVAL: PendingApproval = {
  requestId: 'gallery-1',
  seq: 1,
  tool: 'bash',
  action: 'pip install -r requirements.txt',
  reason: '安装测试依赖才能复现问题',
  risk: 'medium',
  suggestedRule: 'bash(pip install *)',
}

const result = (verdict: string, status = 'done', extra: Partial<ResultMsg> = {}): ResultMsg =>
  ({
    bridge: 'result',
    kind: 'task',
    run_id: `gallery-${verdict}`,
    status,
    run_dir: '/tmp/tw/runs/gallery',
    branch: 'tw/gallery-fix-login-timeout',
    backend: 'docker',
    cost_cny: 0.085,
    steps: 14,
    reason: verdict === 'pass' ? null : '复验时 tests/test_login.py::test_timeout 仍失败',
    summary: '修复登录在网络慢时无限等待的问题：加超时与重试，补 2 个测试。',
    verdict,
    risk_level: 'low',
    clean_env: verdict === 'pass' ? 'verified' : 'failed',
    pr_md: '# 修复登录超时\n\n- 加 3s 超时\n- 失败重试 1 次',
    repo: 'C:/Users/demo/projects/very/long/path/to/repository/name',
    ...extra,
  }) as unknown as ResultMsg

const PELICAN: Partial<ResultMsg> = {
  run_id: 'gallery-pelican',
  reason: null,
  summary: '生成 index.html：用 SVG 画一只骑自行车的鹈鹕，并补了复现测试。',
  risk_level: 'L2',
  clean_env: 'verified',
  repro_status: 'reproduced',
  claim_flags: ['issue_underspecified'],
  anticheat_flags: [],
  regression_blind: false,
  changed_files: ['index.html', 'tests/tw_repro/test_issue_1.py'],
}

const STREAM = '我先读一下 `src/auth/login.ts`，确认超时是在哪里没有生效。\n\n看起来 `fetch` 没有传 `signal`，所以网络慢时会一直等。下一步我会加一个 AbortController，并补测试。\n\n```ts\nconst ctrl = new AbortController()\nconst res = await fetch(url, { signal: ctrl.signal })\n// 30 秒超时\nsetTimeout(() => ctrl.abort(), 30_000)\n```'

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="mb-10">
      <h2 className="mb-3 border-b border-border pb-1.5 font-sans text-[15px] font-semibold text-ink">{title}</h2>
      {children}
    </section>
  )
}

/** 样例页跟应用用同一份偏好：主题（auto 跟系统）与阅读字号；?theme=dark|light 可临时覆盖（批次 2-7 / P2） */
function applyPrefs() {
  const p = getPrefs()
  const q = new URLSearchParams(location.search).get('theme')
  const auto = window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  const root = document.documentElement
  root.dataset.theme = q === 'dark' || q === 'light' ? q : p.theme === 'auto' ? auto : p.theme
  root.style.setProperty('--read-fs', `${p.readingSize}px`)
}

export default function UiGallery() {
  const [n, setN] = useState(0)
  const [, setTick] = useState(0)
  useEffect(applyPrefs, [])
  const [keyOpen, setKeyOpen] = useState(false)
  useEffect(() => {
    const h = setInterval(() => setN((x) => (x >= STREAM.length ? 0 : x + 3)), 80)
    return () => clearInterval(h)
  }, [])
  const theme = document.documentElement.dataset.theme
  return (
    <div className="h-full overflow-y-auto scroll-soft bg-parchment text-ink">
      <div className="mx-auto max-w-[68em] px-8 py-8">
        <header className="mb-8 flex items-center gap-3 font-sans text-[13px] text-sepia">
          <strong className="text-[15px] text-ink">UI 走查样例（仅开发版）</strong>
          <button className="rounded-md border border-border px-2 py-1" onClick={() => {
            document.documentElement.dataset.theme = theme === 'dark' ? 'light' : 'dark'
            setN(0)
            setTick((x) => x + 1)
          }}>切换日 / 夜</button>
          <a className="text-amber underline" href="?">返回应用</a>
        </header>
        <Section id="approval" title="审批卡">
          <ApprovalCard req={APPROVAL} onDecide={async () => {}} />
        </Section>
        <Section id="markdown" title="Markdown + 代码块 + 表格">
          <div className="md selectable"><Markdown text={MD} /></div>
        </Section>
        <Section id="verdict" title="结论卡：通过 / 证据不足 / 未过">
          <div className="space-y-4">
            <ResultCard result={result('pass')} />
            <ResultCard result={result('inconclusive')} />
            {/* 真实 run r_01M4RVEZWKASMK9HYES8RPTFK3（鹈鹕 index.html）：复现已通过，但 Issue 没写验收标准 */}
            <ResultCard result={result('inconclusive', 'done', PELICAN)} />
            <ResultCard result={result('fail', 'failed')} />
          </div>
        </Section>
        <Section id="streaming" title="流式输出">
          {/* 预留整段高度：流式过程中下方内容不被推着跳（走查 r2-1） */}
          <div className="grid">
            <div aria-hidden className="invisible col-start-1 row-start-1"><StreamingText text={STREAM} streaming={false} /></div>
            <div className="col-start-1 row-start-1"><StreamingText text={STREAM.slice(0, n)} streaming={n < STREAM.length} /></div>
          </div>
        </Section>
        <Section id="empty" title="空状态 / API Key 提示">
          <div className="paper-card rounded-2xl px-6 py-8 text-center">
            <p className="font-serif text-[26px] text-ink">今天想修什么？</p>
            <p className="mt-2 text-[13px] text-sepia-muted">还没有连接 DeepSeek，先填 API Key 才能开始。</p>
            <button className="mt-4 rounded-lg bg-amber px-4 py-2 text-[14px] text-cream" onClick={() => setKeyOpen(true)}>填写 API Key</button>
          </div>
          <ApiKeyDialog open={keyOpen} onClose={() => setKeyOpen(false)} onSaved={() => setKeyOpen(false)} />
        </Section>
      </div>
    </div>
  )
}
