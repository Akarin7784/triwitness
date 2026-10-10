/**
 * 界面偏好（UI-21）：模型、思考强度、外观、个人资料、运行设置（沙箱 / ¥ 上限 / 高峰 / 权限）、每个会话的草稿。
 * localStorage 持久化，可订阅。勇士模式（unrestricted）从不落盘：只在内存里为下一个任务“上膛”。
 * 模型只有 deepseek-flash 可选；deepseek-v4-pro 不出现在任何列表里（ADR-0002）。
 */
import { useSyncExternalStore } from 'react'
import { BACKENDS, MAX_COST_CAP, PERMISSION_MODES, type Backend, type PermissionMode } from '../bridge/choices'
import { t as tr } from './i18n'

export type Thinking = 'off' | 'low' | 'medium' | 'high'
export const THINKING_LEVELS: { id: Thinking; label: string }[] = [
  { id: 'off', label: tr('关') },
  { id: 'low', label: tr('低') },
  { id: 'medium', label: tr('中') },
  { id: 'high', label: tr('高') },
]

export interface ModelOption {
  id: string
  name: string
  note: string
  available: boolean
}

/** 可选模型。其他厂商只作“稍后”的灰显占位；v4-pro 永不列出 */
export const MODELS: ModelOption[] = [
  { id: 'deepseek-flash', name: 'DeepSeek Flash', note: tr('快 · 省 · 可思考'), available: true },
  { id: 'qwen', name: tr('通义千问'), note: tr('稍后'), available: false },
  { id: 'glm', name: tr('智谱 GLM'), note: tr('稍后'), available: false },
]

export function isSelectableModel(id: string): boolean {
  return MODELS.some((m) => m.id === id && m.available) && !/v4-pro/i.test(id)
}

export type Theme = 'light' | 'auto' | 'dark'
export type ChatFont = 'serif' | 'sans' | 'system'
export const FONT_SCALES = [0.9, 1, 1.1, 1.2] as const
export type SavedMode = Exclude<PermissionMode, 'unrestricted'>

export type Language = 'zh' | 'en'
export interface CustomStyle {
  id: string
  name: string
  prompt: string
}
/** 预设风格（与 Claude 的 Normal / Concise / Explanatory / Formal 对应） */
export const PRESET_STYLES = [
  { id: 'standard', name: tr('标准'), prompt: '' },
  { id: 'concise', name: tr('简洁'), prompt: '回答简短直接：只给结论与必要步骤，不重复题意，不写客套话。' }, // i18n-ignore: 写给模型
  { id: 'detailed', name: tr('详细'), prompt: '回答详细：解释思路与取舍，给出背景、步骤和例子，便于学习。' }, // i18n-ignore: 写给模型
  { id: 'formal', name: tr('正式'), prompt: '用正式、清晰、结构化的书面语回答，适合直接放进文档或评审。' }, // i18n-ignore: 写给模型
] as const
export const MAX_ARTIFACT_W = 900
export const MIN_ARTIFACT_W = 340

export interface Prefs {
  model: string
  thinking: Thinking
  /** 上次开着的思考档，快捷开关从“关”恢复到它 */
  lastThinking: Exclude<Thinking, 'off'>
  theme: Theme
  chatFont: ChatFont
  fontScale: number
  language: Language
  /** 当前风格：预设 id 或自定义风格 id */
  style: string
  customStyles: CustomStyle[]
  /** 作品侧栏宽度（px，可拖动） */
  artifactWidth: number
  /** 个人资料：怎么称呼你、偏好（本机保存） */
  name: string
  about: string
  backend: Backend
  maxCost: number
  allowPeak: boolean
  permissionMode: SavedMode
  sidebarCollapsed: boolean
}

const KEY = 'tw.prefs'
const DRAFTS = 'tw.drafts'
export const DEFAULTS: Prefs = {
  model: 'deepseek-flash',
  thinking: 'medium',
  lastThinking: 'medium',
  theme: 'light',
  chatFont: 'serif',
  fontScale: 1,
  language: 'zh',
  style: 'standard',
  customStyles: [],
  artifactWidth: 520,
  name: '',
  about: '',
  backend: 'auto',
  maxCost: MAX_COST_CAP,
  allowPeak: false,
  permissionMode: 'auto_edit',
  sidebarCollapsed: false,
}

/** 逐项校验：坏值回默认；v4-pro / 勇士模式 / 超上限一律不可能从存储里读出来 */
function sanitize(p: Prefs, fallback: Prefs = DEFAULTS): Prefs {
  const q = { ...p }
  if (!isSelectableModel(q.model)) q.model = fallback.model
  if (!THINKING_LEVELS.some((t) => t.id === q.thinking)) q.thinking = fallback.thinking
  if (!['light', 'auto', 'dark'].includes(q.theme)) q.theme = fallback.theme
  if (!['serif', 'sans', 'system'].includes(q.chatFont)) q.chatFont = fallback.chatFont
  if (!(FONT_SCALES as readonly number[]).includes(q.fontScale)) q.fontScale = fallback.fontScale
  if (q.language !== 'en') q.language = 'zh'
  q.customStyles = Array.isArray(q.customStyles)
    ? q.customStyles
        .filter((c) => c && typeof c.id === 'string' && typeof c.name === 'string' && typeof c.prompt === 'string')
        .slice(0, 20)
        .map((c) => ({ id: c.id.slice(0, 40), name: c.name.slice(0, 30), prompt: c.prompt.slice(0, 2000) }))
    : []
  if (typeof q.style !== 'string' || !(PRESET_STYLES.some((s) => s.id === q.style) || q.customStyles.some((c) => c.id === q.style))) {
    q.style = fallback.style
  }
  if (typeof q.artifactWidth !== 'number' || !Number.isFinite(q.artifactWidth)) q.artifactWidth = fallback.artifactWidth
  q.artifactWidth = Math.round(Math.min(MAX_ARTIFACT_W, Math.max(MIN_ARTIFACT_W, q.artifactWidth)))
  if (typeof q.name !== 'string') q.name = ''
  if (typeof q.about !== 'string') q.about = ''
  q.name = q.name.slice(0, 40)
  q.about = q.about.slice(0, 2000)
  if (!(BACKENDS as readonly string[]).includes(q.backend)) q.backend = fallback.backend
  if (typeof q.maxCost !== 'number' || !(q.maxCost > 0 && q.maxCost <= MAX_COST_CAP)) q.maxCost = fallback.maxCost
  q.allowPeak = q.allowPeak === true
  if (!(PERMISSION_MODES as readonly string[]).includes(q.permissionMode) || q.permissionMode === ('unrestricted' as string)) {
    q.permissionMode = fallback.permissionMode
  }
  q.sidebarCollapsed = q.sidebarCollapsed === true
  return q
}

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
    const p = sanitize({ ...DEFAULTS, ...raw })
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
  const next = sanitize({ ...prefs, ...patch }, prefs)
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

/** 勇士模式：两步确认后为“下一个任务”上膛（scope=task），起任务时取走；从不写盘 */
let warrior = false
const warriorSubs = new Set<() => void>()
function setWarrior(v: boolean) {
  warrior = v
  for (const s of warriorSubs) s()
}
export function armUnrestricted() {
  setWarrior(true)
}
export function disarmUnrestricted() {
  setWarrior(false)
}
export function takeUnrestricted(): boolean {
  const v = warrior
  if (v) setWarrior(false)
  return v
}
export function useUnrestrictedArmed(): boolean {
  return useSyncExternalStore(
    (fn) => {
      warriorSubs.add(fn)
      return () => warriorSubs.delete(fn)
    },
    () => warrior,
  )
}
