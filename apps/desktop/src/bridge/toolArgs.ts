/**
 * 核心子命令白名单（UI-21 第 3 轮）：与 Rust `files::tool_args_ok` 同一张表，开发桥和测试共用。
 * 只读自检、受控安装（--plan / --yes 只在用户确认后传）、规则编辑。
 */
function pairs(rest: string[], allowed: string[]): Map<string, string> | null {
  if (rest.length % 2) return null
  const m = new Map<string, string>()
  for (let i = 0; i < rest.length; i += 2) {
    const [k, v] = [rest[i], rest[i + 1]]
    if (!allowed.includes(k) || m.has(k) || v.startsWith('--')) return null
    m.set(k, v)
  }
  return m
}

export function toolArgsOk(a: unknown): a is string[] {
  if (!Array.isArray(a) || !a.every((x) => typeof x === 'string')) return false
  const s = a as string[]
  if (s.length === 2 && s[0] === 'doctor' && s[1] === '--json') return true
  if (s.length === 2 && s[0] === 'usage' && s[1] === '--json') return true // 用量页：本地账本（只读）
  if (s.length === 4 && s[0] === 'sandbox' && s[1] === 'install') {
    return ['docker', 'wsl'].includes(s[2]) && ['--plan', '--yes'].includes(s[3])
  }
  if (s[0] !== 'permissions') return false
  const rest = s.slice(2)
  switch (s[1]) {
    case 'list':
      return pairs(rest, ['--repo']) !== null
    case 'validate':
      return pairs(rest, ['--kind', '--rule'])?.size === 2
    case 'add':
    case 'remove': {
      const allowed = ['--kind', '--rule', '--layer', '--repo', ...(s[1] === 'add' ? ['--replace'] : [])]
      const m = pairs(rest, allowed)
      if (!m || !m.has('--kind') || !m.has('--rule')) return false
      if (!['allow', 'ask', 'deny'].includes(m.get('--kind')!)) return false
      const layer = m.get('--layer')
      return layer === undefined || layer === 'user' || layer === 'local'
    }
    default:
      return false
  }
}
