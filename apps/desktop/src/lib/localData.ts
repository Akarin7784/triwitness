/**
 * 隐私（UI-21 第 3 轮）：导出 / 清除本机界面数据。
 * 只碰 localStorage 里 tw.* 的条目——API 密钥在系统凭据库，不在这里，也不会被导出。
 * 磁盘上的任务证据（~/.triwitness/runs）不动：那是复验的底稿，要删请在文件夹里删。
 */
export const HISTORY_KEYS = ['tw.chats', 'tw.live.tasks', 'tw.drafts'] as const

function storage(): Storage | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage
  } catch {
    return null
  }
}

export function collectLocalData(now = new Date()): string {
  const s = storage()
  const data: Record<string, unknown> = {}
  if (s) {
    for (let i = 0; i < s.length; i++) {
      const k = s.key(i)
      if (!k?.startsWith('tw.')) continue
      const raw = s.getItem(k)
      try {
        data[k] = JSON.parse(raw ?? 'null')
      } catch {
        data[k] = raw
      }
    }
  }
  return JSON.stringify({ app: 'triwitness-desktop', exportedAt: now.toISOString(), note: 'local UI data only; API key is in the OS keychain and not included', data }, null, 2)
}

export function exportFileStamp(now = new Date()): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `triwitness-data-${now.getFullYear()}${p(now.getMonth() + 1)}${p(now.getDate())}-${p(now.getHours())}${p(now.getMinutes())}.json`
}

/** 清掉会话记录（会话、任务列表、草稿）；设置和项目保留。返回清掉的条目数。 */
export function clearHistory(): number {
  const s = storage()
  if (!s) return 0
  let n = 0
  for (const k of HISTORY_KEYS) {
    if (s.getItem(k) !== null) n++
    s.removeItem(k)
  }
  return n
}
