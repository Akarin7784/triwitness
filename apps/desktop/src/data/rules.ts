/**
 * 内置权限规则（configs/permissions.default.yaml）的只读视图，设置 → 权限页用。
 * 只解析这份文件用到的子集：顶层 deny / ask / allow 列表，项为字符串或 {rule, backends}。
 */
export interface RuleItem {
  rule: string
  backends?: string[]
  exception: boolean
}
export type RuleKind = 'deny' | 'ask' | 'allow'
export type RuleSet = Record<RuleKind, RuleItem[]>

export function parseRules(yaml: string): RuleSet {
  const out: RuleSet = { deny: [], ask: [], allow: [] }
  let cur: RuleKind | null = null
  for (const raw of yaml.split(/\r?\n/)) {
    const line = raw.replace(/\s+#.*$/, '')
    const top = /^([a-z_]+):\s*$/.exec(line)
    if (top) {
      cur = (['deny', 'ask', 'allow'] as string[]).includes(top[1]) ? (top[1] as RuleKind) : null
      continue
    }
    if (/^\S/.test(line)) cur = null
    if (!cur) continue
    const item = /^\s+-\s+(.+?)\s*$/.exec(line)
    if (!item) continue
    let rule = item[1]
    let backends: string[] | undefined
    const obj = /^\{\s*rule:\s*"([^"]+)"\s*,\s*backends:\s*\[([^\]]*)\]\s*\}$/.exec(rule)
    if (obj) {
      rule = obj[1]
      backends = obj[2].split(',').map((s) => s.trim()).filter(Boolean)
    }
    const exception = rule.includes('(!')
    out[cur].push({ rule: rule.replace('(!', '('), backends, exception })
  }
  return out
}
