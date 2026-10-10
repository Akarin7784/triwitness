/**
 * 快捷键（UI-21）：与 Claude Desktop 同一套。表格同时用于快捷键列表（Ctrl+/）和全局处理。
 * macOS 上 Ctrl 换成 ⌘（metaKey 同样识别）。
 */
export type ShortcutAction =
  | 'newChat'
  | 'search'
  | 'toggleSidebar'
  | 'stop'
  | 'copyLast'
  | 'focusInput'
  | 'upload'
  | 'settings'
  | 'shortcuts'
  | 'nextChat'
  | 'prevChat'
  | 'modelMenu'
  | 'effortMenu'

export interface Shortcut {
  action: ShortcutAction | 'send' | 'newline'
  label: string
  keys: string[]
  group: '常用' | '对话' | '导航'
}

export const SHORTCUTS: Shortcut[] = [
  { action: 'newChat', label: '新会话', keys: ['Ctrl', 'Shift', 'O'], group: '常用' },
  { action: 'search', label: '搜索会话', keys: ['Ctrl', 'K'], group: '常用' },
  { action: 'toggleSidebar', label: '收起 / 展开侧栏', keys: ['Ctrl', 'Shift', 'S'], group: '常用' },
  { action: 'settings', label: '设置', keys: ['Ctrl', ','], group: '常用' },
  { action: 'shortcuts', label: '快捷键', keys: ['Ctrl', '/'], group: '常用' },
  { action: 'send', label: '发送', keys: ['Enter'], group: '对话' },
  { action: 'newline', label: '换行', keys: ['Shift', 'Enter'], group: '对话' },
  { action: 'stop', label: '停止生成', keys: ['Esc'], group: '对话' },
  { action: 'focusInput', label: '聚焦输入框', keys: ['Shift', 'Esc'], group: '对话' },
  { action: 'copyLast', label: '复制最后一条回复', keys: ['Ctrl', 'Shift', 'C'], group: '对话' },
  { action: 'upload', label: '添加文件或图片', keys: ['Ctrl', 'U'], group: '对话' },
  { action: 'modelMenu', label: '切换模型', keys: ['Ctrl', 'Shift', 'I'], group: '对话' },
  { action: 'effortMenu', label: '思考强度', keys: ['Ctrl', 'Shift', 'E'], group: '对话' },
  { action: 'nextChat', label: '下一个会话', keys: ['Ctrl', 'Shift', ']'], group: '导航' },
  { action: 'prevChat', label: '上一个会话', keys: ['Ctrl', 'Shift', '['], group: '导航' },
]

type KeyLike = Pick<KeyboardEvent, 'key' | 'code' | 'ctrlKey' | 'metaKey' | 'shiftKey' | 'altKey'>

/** 按键 → 动作（纯函数，便于单测）。Esc 只在没按修饰键时算“停止” */
export function matchShortcut(e: KeyLike): ShortcutAction | null {
  if (e.altKey) return null
  const mod = e.ctrlKey || e.metaKey
  const k = e.key.toLowerCase()
  if (k === 'escape') return mod ? null : e.shiftKey ? 'focusInput' : 'stop'
  if (!mod) return null
  if (e.shiftKey) {
    if (e.code === 'BracketRight' || k === ']' || k === '}') return 'nextChat'
    if (e.code === 'BracketLeft' || k === '[' || k === '{') return 'prevChat'
    const byCode = /^Key([A-Z])$/.exec(e.code)?.[1]?.toLowerCase() ?? k
    return ({ o: 'newChat', s: 'toggleSidebar', c: 'copyLast', i: 'modelMenu', e: 'effortMenu' } as const)[
      byCode as 'o'
    ] ?? null
  }
  if (k === 'k') return 'search'
  if (k === 'u') return 'upload'
  if (k === ',' || e.code === 'Comma') return 'settings'
  if (k === '/' || e.code === 'Slash') return 'shortcuts'
  return null
}

export const isMac = typeof navigator !== 'undefined' && /Mac/i.test(navigator.platform)
export function keyLabel(k: string): string {
  if (!isMac) return k
  return ({ Ctrl: '⌘', Shift: '⇧', Enter: '↩', Esc: 'esc' } as Record<string, string>)[k] ?? k
}
