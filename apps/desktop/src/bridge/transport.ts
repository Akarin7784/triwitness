/**
 * 核心传输层（UI-10）：Tauri 后端（invoke + 事件）或开发桥（Vite 插件，HTTP + SSE，仅 TW_DEV_BRIDGE=1）。
 * 两者同一套 tw-bridge/1 行协议；浏览器预览里没有核心时返回 null。
 */
import { invoke } from '@tauri-apps/api/core'
import { listen } from '@tauri-apps/api/event'
import type { CoreMode } from './protocol'

export interface StartOptions {
  repo: string
  issue: string
  mode: CoreMode
  model?: string
  thinking?: string
}

export interface CoreTransport {
  readonly kind: 'tauri' | 'dev'
  start(opts: StartOptions): Promise<string>
  send(key: string, line: string): Promise<void>
  cancel(key: string): Promise<void>
  readRun(runDir: string, afterSeq: number): Promise<string[]>
  /** 进程还在（例如界面刷新后）→ 可以重新接上实时流 */
  alive(key: string): Promise<boolean>
  /** 订阅某任务的输出行与退出；返回退订 */
  attach(key: string, onLine: (line: string) => void, onExit: (code: number | null) => void): Promise<() => void>
}

function inTauri(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window
}

class TauriTransport implements CoreTransport {
  readonly kind = 'tauri' as const

  async start(o: StartOptions) {
    return invoke<string>('core_start', {
      repo: o.repo,
      issue: o.issue,
      mode: o.mode,
      model: o.model ?? null,
      thinking: o.thinking ?? null,
    })
  }

  async send(key: string, line: string) {
    await invoke('core_send', { key, line })
  }

  async cancel(key: string) {
    await invoke('core_cancel', { key })
  }

  async readRun(runDir: string, afterSeq: number) {
    return invoke<string[]>('core_read_run', { runDir, afterSeq })
  }

  async alive(key: string) {
    return invoke<boolean>('core_alive', { key })
  }

  async attach(key: string, onLine: (l: string) => void, onExit: (c: number | null) => void) {
    const un1 = await listen<{ key: string; line: string }>('tw://line', (e) => {
      if (e.payload.key === key) onLine(e.payload.line)
    })
    const un2 = await listen<{ key: string; code: number | null }>('tw://exit', (e) => {
      if (e.payload.key === key) onExit(e.payload.code)
    })
    return () => {
      un1()
      un2()
    }
  }
}

class DevTransport implements CoreTransport {
  readonly kind = 'dev' as const

  private async post<T>(path: string, body: unknown): Promise<T> {
    const r = await fetch(`/__tw/${path}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = (await r.json()) as T & { error?: string }
    if (!r.ok) throw new Error(data.error ?? `HTTP ${r.status}`)
    return data
  }

  async start(o: StartOptions) {
    return (await this.post<{ key: string }>('start', o)).key
  }

  async send(key: string, line: string) {
    await this.post('send', { key, line })
  }

  async cancel(key: string) {
    await this.post('cancel', { key })
  }

  async readRun(runDir: string, afterSeq: number) {
    return (await this.post<{ lines: string[] }>('read', { runDir, afterSeq })).lines
  }

  async alive(key: string) {
    return (await this.post<{ alive: boolean }>('alive', { key })).alive
  }

  async attach(key: string, onLine: (l: string) => void, onExit: (c: number | null) => void) {
    const es = new window.EventSource(`/__tw/stream?key=${encodeURIComponent(key)}`)
    es.onmessage = (e) => onLine(e.data)
    es.addEventListener('exit', (e) => {
      onExit(JSON.parse((e as MessageEvent).data).code)
      es.close()
    })
    return () => es.close()
  }
}

let cached: Promise<CoreTransport | null> | null = null

/** Tauri 里用后端；开发服务器开了桥就用 HTTP；否则 null（界面照常，只是不能起任务） */
export function getTransport(): Promise<CoreTransport | null> {
  cached ??= (async () => {
    if (inTauri()) return new TauriTransport()
    try {
      const r = await fetch('/__tw/health')
      if (r.ok && (await r.json()).bridge === 'tw-bridge/1') return new DevTransport()
    } catch {
      /* 没有开发桥 */
    }
    return null
  })()
  return cached
}
