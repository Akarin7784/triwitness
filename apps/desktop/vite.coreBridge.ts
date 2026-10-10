/**
 * 开发桥（UI-10）：浏览器预览 / 截图 / e2e 用，等价于 Tauri 后端的 core_* 命令。
 * 只在 `npm run dev` 且 TW_DEV_BRIDGE=1 时启用（只绑本机）；正式构建不包含。
 *   GET  /__tw/health            → { bridge: 'tw-bridge/1' }
 *   POST /__tw/start {repo,issue,mode} → { key }
 *   GET  /__tw/stream?key=       → SSE：每行一条 message；结束发 event: exit
 *   POST /__tw/send {key,line} · /__tw/cancel {key} · /__tw/alive {key} · /__tw/read {runDir,afterSeq}
 * 核心命令：TW_CORE（JSON 数组），默认 `uv run --project <仓库根> tw`。
 */
import { spawn, type ChildProcess } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { createInterface } from 'node:readline'
import type { IncomingMessage, ServerResponse } from 'node:http'
import type { Plugin } from 'vite'

interface Task {
  child: ChildProcess
  lines: string[]
  exit: number | null | undefined
  subs: Set<ServerResponse>
}

export function runArgs(repo: string, issue: string, mode: string): string[] {
  const a = ['run', '--jsonl', '--repo', repo]
  if (issue.trim()) a.push('--issue', issue)
  if (mode === 'demo') a.push('--demo')
  if (mode === 'live') a.push('--live')
  return a
}

export function readRun(runDir: string, afterSeq: number): string[] {
  const text = readFileSync(join(runDir, 'trajectory.jsonl'), 'utf8')
  return text.split(/\r?\n/).filter((l) => {
    try {
      return (JSON.parse(l) as { seq?: number }).seq! > afterSeq
    } catch {
      return false
    }
  })
}

function body(req: IncomingMessage): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    let raw = ''
    req.on('data', (c) => (raw += c))
    req.on('end', () => {
      try {
        resolve(raw ? JSON.parse(raw) : {})
      } catch (e) {
        reject(e)
      }
    })
  })
}

function json(res: ServerResponse, code: number, data: unknown) {
  res.statusCode = code
  res.setHeader('content-type', 'application/json; charset=utf-8')
  res.end(JSON.stringify(data))
}

export function coreBridge(repoRoot: string): Plugin {
  const tasks = new Map<string, Task>()
  let n = 0
  const core = (): string[] => {
    try {
      const v = JSON.parse(process.env.TW_CORE ?? '')
      if (Array.isArray(v) && v.length) return v.map(String)
    } catch {
      /* 默认 */
    }
    return ['uv', 'run', '--project', repoRoot, 'tw']
  }
  const send = (res: ServerResponse, line: string) => res.write(`data: ${line}\n\n`)
  const sendExit = (res: ServerResponse, code: number | null) =>
    res.write(`event: exit\ndata: ${JSON.stringify({ code })}\n\n`)

  return {
    name: 'tw-core-bridge',
    apply: 'serve',
    configureServer(server) {
      if (process.env.TW_DEV_BRIDGE !== '1') return
      server.middlewares.use('/__tw', async (req, res) => {
        const url = new URL(req.url ?? '/', 'http://localhost')
        try {
          if (url.pathname === '/health') return json(res, 200, { bridge: 'tw-bridge/1' })
          if (url.pathname === '/start' && req.method === 'POST') {
            const b = await body(req)
            const [cmd, ...pre] = core()
            const child = spawn(cmd, [...pre, ...runArgs(String(b.repo ?? ''), String(b.issue ?? ''), String(b.mode ?? 'demo'))], {
              env: { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' },
              stdio: ['pipe', 'pipe', 'pipe'],
              windowsHide: true,
            })
            const key = `d${++n}`
            const t: Task = { child, lines: [], exit: undefined, subs: new Set() }
            tasks.set(key, t)
            createInterface({ input: child.stdout! }).on('line', (line) => {
              if (!line.trim()) return
              t.lines.push(line)
              for (const s of t.subs) send(s, line)
            })
            child.stderr!.on('data', () => {})
            child.on('close', (code) => {
              t.exit = code
              for (const s of t.subs) {
                sendExit(s, code)
                s.end()
              }
              t.subs.clear()
            })
            child.on('error', (e) => {
              t.lines.push(JSON.stringify({ bridge: 'error', message: String(e) }))
            })
            return json(res, 200, { key })
          }
          if (url.pathname === '/stream') {
            const t = tasks.get(url.searchParams.get('key') ?? '')
            if (!t) return json(res, 404, { error: '任务不存在' })
            res.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache', connection: 'keep-alive' })
            for (const l of t.lines) send(res, l)
            if (t.exit !== undefined) {
              sendExit(res, t.exit)
              return res.end()
            }
            t.subs.add(res)
            req.on('close', () => t.subs.delete(res))
            return
          }
          if (url.pathname === '/send' && req.method === 'POST') {
            const b = await body(req)
            const t = tasks.get(String(b.key))
            if (!t || t.exit !== undefined) return json(res, 410, { error: '任务已结束' })
            t.child.stdin!.write(String(b.line).trim() + '\n')
            return json(res, 200, { ok: true })
          }
          if (url.pathname === '/cancel' && req.method === 'POST') {
            const b = await body(req)
            const t = tasks.get(String(b.key))
            if (!t || t.exit !== undefined) return json(res, 410, { error: '任务已结束' })
            t.child.stdin!.write('{"cmd":"cancel"}\n')
            setTimeout(() => t.exit === undefined && t.child.kill(), 10_000)
            return json(res, 200, { ok: true })
          }
          if (url.pathname === '/alive' && req.method === 'POST') {
            const t = tasks.get(String((await body(req)).key))
            return json(res, 200, { alive: !!t && t.exit === undefined })
          }
          if (url.pathname === '/read' && req.method === 'POST') {
            const b = await body(req)
            return json(res, 200, { lines: readRun(String(b.runDir), Number(b.afterSeq ?? -1)) })
          }
          return json(res, 404, { error: 'not found' })
        } catch (e) {
          return json(res, 500, { error: String(e) })
        }
      })
    },
  }
}
