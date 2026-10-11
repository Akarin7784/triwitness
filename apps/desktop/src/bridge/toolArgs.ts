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

const RUN_ID = /^r_[0-9A-HJKMNP-TV-Z]{26}$/

/** `tw pr plan|open`：--run 必须是合法 run_id；open 必须带 --yes（审批卡确认后才传） */
function prArgsOk(rest: string[], open: boolean): boolean {
  let run = false
  let yes = false
  for (let i = 0; i < rest.length; i++) {
    const k = rest[i]
    if (k === '--json') continue
    if (open && k === '--yes') {
      yes = true
      continue
    }
    if (open && k === '--draft') continue
    if (k === '--run' || k === '--repo' || k === '--base') {
      const v = rest[i + 1]
      if (v === undefined || v === '' || v.startsWith('--')) return false
      if (k === '--run') {
        if (!RUN_ID.test(v)) return false
        run = true
      }
      i++
      continue
    }
    return false
  }
  return run && (yes || !open)
}

export function toolArgsOk(a: unknown): a is string[] {
  if (!Array.isArray(a) || !a.every((x) => typeof x === 'string')) return false
  const s = a as string[]
  if (s.length === 2 && s[0] === 'doctor' && s[1] === '--json') return true
  if (s.length === 2 && s[0] === 'usage' && s[1] === '--json') return true // 用量页：本地账本（只读）
  if (s.length === 4 && s[0] === 'sandbox' && s[1] === 'install') {
    return ['docker', 'wsl'].includes(s[2]) && ['--plan', '--yes'].includes(s[3])
  }
  if (s[0] === 'pr' && (s[1] === 'plan' || s[1] === 'open')) return prArgsOk(s.slice(2), s[1] === 'open')
  // 诊断包：只写 $TW_HOME/diagnostics（不放行 --out），可选单个合法运行 id
  if (s[0] === 'diag' && s[1] === 'export') {
    if (s.length === 3) return s[2] === '--json'
    return s.length === 5 && s[2] === '--run' && RUN_ID.test(s[3]) && s[4] === '--json'
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
