/**
 * 界面偏好（UI-20）：模型、思考强度、每个会话的草稿。localStorage 持久化，可订阅。
 * 模型只有 deepseek-flash 可选；deepseek-v4-pro 不出现在任何列表里（ADR-0002）。
 */
import { useSyncExternalStore } from 'react'

export type Thinking = 'off' | 'low' | 'medium' | 'high'
export const THINKING_LEVELS: { id: Thinking; label: string }[] = [
  { id: 'off', label: '关' },
  { id: 'low', label: '低' },
  { id: 'medium', label: '中' },
  { id: 'high', label: '高' },
]

export interface ModelOption {
  id: string
  name: string
  note: string
  available: boolean
}

/** 可选模型。其他厂商只作“稍后”的灰显占位；v4-pro 永不列出 */
export const MODELS: ModelOption[] = [
  { id: 'deepseek-flash', name: 'DeepSeek Flash', note: '快 · 省 · 可思考', available: true },
  { id: 'qwen', name: '通义千问', note: '稍后', available: false },
  { id: 'glm', name: '智谱 GLM', note: '稍后', available: false },
]

export function isSelectableModel(id: string): boolean {
  return MODELS.some((m) => m.id === id && m.available) && !/v4-pro/i.test(id)
}

interface Prefs {
  model: string
  thinking: Thinking
  /** 上次开着的思考档，快捷开关从“关”恢复到它 */
  lastThinking: Exclude<Thinking, 'off'>
}

const KEY = 'tw.prefs'
const DRAFTS = 'tw.drafts'
const DEFAULTS: Prefs = { model: 'deepseek-flash', thinking: 'medium', lastThinking: 'medium' }

function store(): Storage | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage
  } catch {
    return null
  }
}

function load(): Prefs {
  try {
    const raw = JSON.parse(store()?.getItem(KEY) ?? '{}') as Partial<Prefs>
    const p = { ...DEFAULTS, ...raw }
    if (!isSelectableModel(p.model)) p.model = DEFAULTS.model
    if (!THINKING_LEVELS.some((t) => t.id === p.thinking)) p.thinking = DEFAULTS.thinking
    if (!THINKING_LEVELS.some((t) => t.id === p.lastThinking) || p.lastThinking === ('off' as Thinking)) {
      p.lastThinking = DEFAULTS.lastThinking
    }
    return p
  } catch {
    return DEFAULTS
  }
}

let prefs = load()
const subs = new Set<() => void>()

export function getPrefs(): Prefs {
  return prefs
}

export function setPrefs(patch: Partial<Prefs>) {
  const next = { ...prefs, ...patch }
  if (!isSelectableModel(next.model)) next.model = prefs.model
  if (next.thinking !== 'off') next.lastThinking = next.thinking
  prefs = next
  store()?.setItem(KEY, JSON.stringify(prefs))
  for (const s of subs) s()
}

export function usePrefs(): Prefs {
  return useSyncExternalStore(
    (fn) => {
      subs.add(fn)
      return () => subs.delete(fn)
    },
    () => prefs,
  )
}

/** 测试用：重读存储 */
export function reloadPrefs() {
  prefs = load()
}

function drafts(): Record<string, string> {
  try {
    const v = JSON.parse(store()?.getItem(DRAFTS) ?? '{}')
    return v && typeof v === 'object' ? (v as Record<string, string>) : {}
  } catch {
    return {}
  }
}

export function getDraft(key: string): string {
  return drafts()[key] ?? ''
}

export function setDraft(key: string, text: string) {
  const d = drafts()
  if (text) d[key] = text
  else delete d[key]
  store()?.setItem(DRAFTS, JSON.stringify(d))
}
