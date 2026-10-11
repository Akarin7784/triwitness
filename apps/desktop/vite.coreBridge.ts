/**
 * 开发桥（UI-10）：浏览器预览 / 截图 / e2e 用，等价于 Tauri 后端的 core_* 命令。
 * 只在 `npm run dev` 且 TW_DEV_BRIDGE=1 时启用（只绑本机）；正式构建不包含。
 *   GET  /__tw/health            → { bridge: 'tw-bridge/1' }
 *   POST /__tw/start {repo,issue,mode,parentRun,...RunChoices} → { key }
 *   GET  /__tw/stream?key=       → SSE：每行一条 message；结束发 event: exit
 *   POST /__tw/send {key,line} · /__tw/cancel {key} · /__tw/alive {key} · /__tw/read {runDir,afterSeq}
 *   POST /__tw/attach {name,dataB64} → {path,name,size} · /__tw/artifact {runDir,name} → {text|null}
 *   POST /__tw/tool {args} → {code,stdout,stderr}（白名单同 Rust tool_args_ok）
 * 核心命令：TW_CORE（JSON 数组），默认 `uv run --project <仓库根> tw`。
 */
import { spawn, spawnSync, type ChildProcess } from 'node:child_process'
import { existsSync, mkdirSync, readFileSync, realpathSync, statSync, writeFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { join, sep } from 'node:path'
import { createInterface } from 'node:readline'
import type { IncomingMessage, ServerResponse } from 'node:http'
import type { Plugin } from 'vite'
import { choiceArgs } from './src/bridge/choices.ts'
import { toolArgsOk } from './src/bridge/toolArgs.ts'

const ARTIFACTS = ['patch.diff', 'pr.md', 'cost.md', 'finish.json', 'summary.json']
const twHome = () => process.env.TW_HOME?.trim() || join(homedir(), '.triwitness')

export function cleanName(name: string): string {
  let s = [...(name.split(/[\\/]/).pop() ?? '')]
    .map((c) => (c.charCodeAt(0) < 32 || '<>:"|?*'.includes(c) ? '_' : c))
    .join('')
    .trim()
    .replace(/^\.+|\.+$/g, '')
  if ([...s].length > 120) s = [...s].slice(0, 100).join('') + (/(\.[^.]{1,10})$/.exec(name)?.[1] ?? '')
  const up = (s.split('.')[0] ?? '').toUpperCase()
  if (!s || ['CON', 'PRN', 'AUX', 'NUL'].includes(up) || /^(COM|LPT)\d$/.test(up)) return s ? `file_${s}` : 'file'
  return s
}

function inside(root: string, p: string): boolean {
  try {
    const r = realpathSync(root)
    const f = realpathSync(p)
    return (f + sep).startsWith(r + sep) && f !== r && statSync(f).isFile()
  } catch {
    return false
  }
}

/** 附件 / 用户说明 → --attach / --guidance-file（与 Rust input_args 一致） */
function inputArgs(b: Record<string, unknown>, key: string): string[] {
  const a: string[] = []
  const root = join(twHome(), 'attachments')
  const list = Array.isArray(b.attachments) ? b.attachments.slice(0, 20) : []
  for (const p of list) if (typeof p === 'string' && inside(root, p)) a.push('--attach', p)
  const g = typeof b.guidance === 'string' ? b.guidance.trim() : ''
  if (g) {
    const dir = join(root, 'guidance')
    mkdirSync(dir, { recursive: true })
    const f = join(dir, `dev-${process.pid}-${key}.md`)
    writeFileSync(f, [...g].slice(0, 8000).join(''), 'utf8')
    a.push('--guidance-file', f)
  }
  return a
}

interface Task {
  child: ChildProcess
  lines: string[]
  exit: number | null | undefined
  subs: Set<ServerResponse>
}

/** 与 Rust run_args 一致；开发桥额外允许 demo（仅开发 / 测试，正式版核心不含） */
export function runArgs(repo: string, issue: string, mode: string, parentRun = ''): string[] {
  const a = ['run', '--jsonl']
  if (repo.trim()) a.push('--repo', repo)
  if (issue.trim()) a.push('--issue', issue)
  if (/^r_[0-9A-Za-z]{8,40}$/.test(parentRun)) a.push('--parent-run', parentRun)
  if (mode === 'demo') a.push('--demo')
  else if (mode !== 'replay') a.push('--live')
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
            const key = `d${++n}`
            const args = [...runArgs(String(b.repo ?? ''), String(b.issue ?? ''), String(b.mode ?? 'live'), String(b.parentRun ?? '')), ...choiceArgs(b), ...inputArgs(b, key)]
            const child = spawn(cmd, [...pre, ...args], {
              env: { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' },
              stdio: ['pipe', 'pipe', 'pipe'],
              windowsHide: true,
            })
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
          if (url.pathname === '/attach' && req.method === 'POST') {
            const b = await body(req)
            const bytes = Buffer.from(String(b.dataB64 ?? ''), 'base64')
            if (bytes.length > 10 * 1024 * 1024) return json(res, 413, { error: '附件超过 10 MB' })
            const name = cleanName(String(b.name ?? ''))
            const dir = join(twHome(), 'attachments', `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`)
            mkdirSync(dir, { recursive: true })
            const path = join(dir, name)
            writeFileSync(path, bytes)
            return json(res, 200, { path, name, size: bytes.length })
          }
          if (url.pathname === '/artifact' && req.method === 'POST') {
            const b = await body(req)
            const name = String(b.name)
            if (!ARTIFACTS.includes(name)) return json(res, 403, { error: '不允许读取该文件' })
            const runDir = String(b.runDir)
            const runs = join(twHome(), 'runs')
            const f = join(runDir, name)
            if (!existsSync(f)) return json(res, 200, { text: null })
            if (!inside(runs, f)) return json(res, 403, { error: '不在任务目录内' })
            return json(res, 200, { text: readFileSync(f, 'utf8') })
          }
          if (url.pathname === '/tool' && req.method === 'POST') {
            const b = await body(req)
            if (!toolArgsOk(b.args)) return json(res, 403, { error: '不允许的核心命令' })
            const [cmd, ...pre] = core()
            const r = spawnSync(cmd, [...pre, ...b.args], {
              env: { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' },
              encoding: 'utf8',
              windowsHide: true,
              timeout: 30 * 60_000,
            })
            return json(res, 200, { code: r.status, stdout: r.stdout ?? '', stderr: (r.stderr ?? '').slice(-2000) })
          }
          return json(res, 404, { error: 'not found' })
        } catch (e) {
          return json(res, 500, { error: String(e) })
        }
      })
    },
  }
}
