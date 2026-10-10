/**
 * 本次任务的选择（UI-21）：输入框（模型 / 思考强度）+ 设置页（沙箱后端 / ¥ 上限 / 权限模式 / 高峰）。
 * 与 Rust `choice_args` 同一张白名单；核心那边还会再拒一次。纯函数，开发桥和测试共用。
 */
export interface RunChoices {
  model?: string
  thinking?: string
  backend?: string
  maxCost?: number
  permissionMode?: string
  confirmUnrestricted?: string
  allowPeak?: boolean
  /** attach_save 返回的路径；桥那边只接受 ~/.triwitness/attachments/ 之内 */
  attachments?: string[]
  /** 个人偏好 + 风格 + 项目说明（纯文本） */
  guidance?: string
}

export const UNRESTRICTED_PHRASE = '我了解风险'
/** 与 core Budget.for_run() 一致：只能调低 */
export const MAX_COST_CAP = 1.0
export const PERMISSION_MODES = ['plan', 'ask', 'auto_edit', 'auto', 'full_access', 'unrestricted'] as const
export type PermissionMode = (typeof PERMISSION_MODES)[number]
export const BACKENDS = ['auto', 'docker', 'none'] as const
export type Backend = (typeof BACKENDS)[number]

export function choiceArgs(c: Record<string, unknown> | RunChoices = {}): string[] {
  const a: string[] = []
  const o = c as Record<string, unknown>
  if (o.model === 'deepseek-flash') a.push('--model', 'deepseek-flash')
  if (typeof o.thinking === 'string' && ['off', 'low', 'medium', 'high'].includes(o.thinking)) a.push('--thinking', o.thinking)
  if (typeof o.backend === 'string' && (BACKENDS as readonly string[]).includes(o.backend)) a.push('--backend', o.backend)
  if (typeof o.maxCost === 'number' && Number.isFinite(o.maxCost) && o.maxCost > 0 && o.maxCost <= MAX_COST_CAP) {
    a.push('--max-cost', o.maxCost.toFixed(2))
  }
  const m = o.permissionMode
  if (typeof m === 'string' && ['plan', 'ask', 'auto_edit', 'auto', 'full_access'].includes(m)) a.push('--permission-mode', m)
  else if (m === 'unrestricted' && o.confirmUnrestricted === UNRESTRICTED_PHRASE) {
    a.push('--permission-mode', 'unrestricted', '--confirm-unrestricted', UNRESTRICTED_PHRASE)
  }
  if (o.allowPeak === true) a.push('--allow-peak')
  return a
}
