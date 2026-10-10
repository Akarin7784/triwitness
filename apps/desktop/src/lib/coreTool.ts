/** 调核心的白名单子命令（doctor / sandbox install / permissions），解析第一行 JSON */
import { getTransport } from '../bridge/transport'
import { t as tr } from './i18n'

export type ToolResult<T> = { ok: true; data: T } | { ok: false; error: string; offline?: boolean }

export function parseToolStdout<T>(stdout: string): T | null {
  const line = stdout.split(/\r?\n/).find((l) => l.trim().startsWith('{'))
  if (!line) return null
  try {
    return JSON.parse(line) as T
  } catch {
    return null
  }
}

export async function coreTool<T>(args: string[]): Promise<ToolResult<T>> {
  const t = await getTransport()
  if (!t) return { ok: false, error: tr('未连接核心'), offline: true }
  try {
    const out = await t.tool(args)
    const data = parseToolStdout<T & { ok?: boolean; error?: string }>(out.stdout)
    if (!data) return { ok: false, error: out.stderr.trim().split('\n').pop() || tr('核心退出码 {0}', String(out.code)) }
    if (data.ok === false) return { ok: false, error: data.error ?? tr('失败') }
    return { ok: true, data }
  } catch (e) {
    return { ok: false, error: String(e instanceof Error ? e.message : e) }
  }
}
