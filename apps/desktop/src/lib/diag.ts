/**
 * 诊断包（v1.0）：`tw diag export` 把 system / 用量 / 日志 / 运行目录打成 zip，密钥脱敏，只留在本机
 * （$TW_HOME/diagnostics/），由你自己决定发给谁。桌面端只能导出到默认目录（白名单不放行 --out）。
 */
import { coreTool, type ToolResult } from './coreTool'

export interface DiagExport {
  path: string
  files: number
  skipped: number
  redactions: number
  runs: string[]
  bytes: number
}

export function diagArgs(runId?: string | null): string[] {
  return runId ? ['diag', 'export', '--run', runId, '--json'] : ['diag', 'export', '--json']
}

export const exportDiagnostics = (runId?: string | null): Promise<ToolResult<DiagExport>> => coreTool<DiagExport>(diagArgs(runId))
