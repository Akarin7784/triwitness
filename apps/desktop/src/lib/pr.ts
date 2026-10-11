/**
 * 开 PR（v1.0）：结论卡「开 PR」→ 审批卡（`tw pr plan`，不联网）→ 用户确认 → `tw pr open --yes`。
 * 令牌在系统凭据库里（kind = github），只由 Rust 注入 `tw pr …` 子进程，前端拿不到明文。
 */
import { coreTool, type ToolResult } from './coreTool'

export const GITHUB_TOKEN_URL = 'https://github.com/settings/personal-access-tokens/new'

export interface PrPlan {
  run_id: string
  repo_path: string
  remote: string
  owner: string
  repo: string
  full_name: string
  head: string
  base: string
  title: string
  body_preview: string
  commits: number
  files: string[]
  /** token = 凭据库里的令牌；gh = 本机已登录的 gh；null = 还没有授权 */
  auth: 'token' | 'gh' | null
  existing_url: string | null
  guidance: string
  token_url: string
}

export interface PrOpened {
  url: string
  number: number
  created: boolean
  repo: string
  head: string
  base: string
  title: string
}

export function prArgs(sub: 'plan' | 'open', runId: string, repo?: string | null, base?: string | null): string[] {
  const a = ['pr', sub, '--run', runId]
  if (repo) a.push('--repo', repo)
  if (base) a.push('--base', base)
  if (sub === 'open') a.push('--yes')
  a.push('--json')
  return a
}

export const planPr = (runId: string, repo?: string | null, base?: string | null): Promise<ToolResult<PrPlan>> =>
  coreTool<PrPlan>(prArgs('plan', runId, repo, base))

/** 只在用户在审批卡上点了确认之后调用 */
export const openPr = (runId: string, repo?: string | null, base?: string | null): Promise<ToolResult<PrOpened>> =>
  coreTool<PrOpened>(prArgs('open', runId, repo, base))
