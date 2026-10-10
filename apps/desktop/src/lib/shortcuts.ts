import { t } from './i18n'
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
  group: '常用' | '对话' | '导航' // i18n-ignore: 分组键
}

export const SHORTCUTS: Shortcut[] = [
  { action: 'newChat', label: t('新会话'), keys: ['Ctrl', 'Shift', 'O'], group: '常用' }, // i18n-ignore: 分组键
  { action: 'search', label: t('搜索会话'), keys: ['Ctrl', 'K'], group: '常用' }, // i18n-ignore: 分组键
  { action: 'toggleSidebar', label: t('收起 / 展开侧栏'), keys: ['Ctrl', 'Shift', 'S'], group: '常用' }, // i18n-ignore: 分组键
  { action: 'settings', label: t('设置'), keys: ['Ctrl', ','], group: '常用' }, // i18n-ignore: 分组键
  { action: 'shortcuts', label: t('快捷键'), keys: ['Ctrl', '/'], group: '常用' }, // i18n-ignore: 分组键
  { action: 'send', label: t('发送'), keys: ['Enter'], group: '对话' }, // i18n-ignore: 分组键
  { action: 'newline', label: t('换行'), keys: ['Shift', 'Enter'], group: '对话' }, // i18n-ignore: 分组键
  { action: 'stop', label: t('停止生成'), keys: ['Esc'], group: '对话' }, // i18n-ignore: 分组键
  { action: 'focusInput', label: t('聚焦输入框'), keys: ['Shift', 'Esc'], group: '对话' }, // i18n-ignore: 分组键
  { action: 'copyLast', label: t('复制最后一条回复'), keys: ['Ctrl', 'Shift', 'C'], group: '对话' }, // i18n-ignore: 分组键
  { action: 'upload', label: t('添加文件或图片'), keys: ['Ctrl', 'U'], group: '对话' }, // i18n-ignore: 分组键
  { action: 'modelMenu', label: t('切换模型'), keys: ['Ctrl', 'Shift', 'I'], group: '对话' }, // i18n-ignore: 分组键
  { action: 'effortMenu', label: t('思考强度'), keys: ['Ctrl', 'Shift', 'E'], group: '对话' }, // i18n-ignore: 分组键
  { action: 'nextChat', label: t('下一个会话'), keys: ['Ctrl', 'Shift', ']'], group: '导航' }, // i18n-ignore: 分组键
  { action: 'prevChat', label: t('上一个会话'), keys: ['Ctrl', 'Shift', '['], group: '导航' }, // i18n-ignore: 分组键
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
