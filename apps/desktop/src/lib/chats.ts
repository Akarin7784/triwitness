/**
 * 会话层（UI-21）：侧栏的重命名 / 星标 / 删除、重试与编辑后重发产生的版本、赞踩反馈。
 * 一个会话 = 一个根 key（fixture: / live: / local:）；重试 / 编辑各起一个新任务，作为该会话的新版本。
 * localStorage 持久化，可订阅。
 */
import { useSyncExternalStore } from 'react'

export interface ChatOverlay {
  title?: string
  starred?: boolean
  deleted?: boolean
}
export type VersionKind = 'retry' | 'edit'
export interface Versions {
  /** list[0] 是根 key 自己 */
  list: string[]
  sel: number
  /** 与 list 对齐；list[0] 为 null */
  kinds?: (VersionKind | null)[]
}
export type Rating = 'up' | 'down'
export interface Feedback {
  rating: Rating
  note?: string
}

interface State {
  overlay: Record<string, ChatOverlay>
  versions: Record<string, Versions>
  feedback: Record<string, Feedback>
}

const KEY = 'tw.chats'

function storage(): Storage | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage
  } catch {
    return null
  }
}

function load(): State {
  try {
    const v = JSON.parse(storage()?.getItem(KEY) ?? '{}') as Partial<State>
    return { overlay: v.overlay ?? {}, versions: v.versions ?? {}, feedback: v.feedback ?? {} }
  } catch {
    return { overlay: {}, versions: {}, feedback: {} }
  }
}

let state: State = load()
const subs = new Set<() => void>()

function commit(next: State) {
  state = next
  storage()?.setItem(KEY, JSON.stringify(next))
  for (const s of subs) s()
}

export function useChats(): State {
  return useSyncExternalStore(
    (fn) => {
      subs.add(fn)
      return () => subs.delete(fn)
    },
    () => state,
  )
}

export function getChats(): State {
  return state
}

/** 测试用 */
export function reloadChats() {
  state = load()
}

function patchOverlay(key: string, patch: ChatOverlay) {
  commit({ ...state, overlay: { ...state.overlay, [key]: { ...state.overlay[key], ...patch } } })
}

export function renameChat(key: string, title: string) {
  const t = title.trim().slice(0, 80)
  patchOverlay(key, { title: t || undefined })
}

export function toggleStar(key: string) {
  patchOverlay(key, { starred: !state.overlay[key]?.starred })
}

/** 删除：标记隐藏（fixture 无法真删）；返回该会话所有版本 key，调用方据此清理真实任务 */
export function deleteChat(key: string): string[] {
  const all = state.versions[key]?.list ?? [key]
  const versions = { ...state.versions }
  delete versions[key]
  commit({ ...state, versions, overlay: { ...state.overlay, [key]: { ...state.overlay[key], deleted: true } } })
  return all
}

/** 某 key 所属会话的根（不是任何会话的版本就是它自己） */
export function rootOf(key: string, s: State = state): string {
  for (const [root, v] of Object.entries(s.versions)) if (v.list.includes(key)) return root
  return key
}

/** 是某个会话的非首个版本：侧栏不单独列出 */
export function isVersionChild(key: string, s: State = state): boolean {
  return Object.entries(s.versions).some(([root, v]) => root !== key && v.list.includes(key))
}

/** 会话当前显示的版本 key */
export function currentVersion(root: string, s: State = state): string {
  const v = s.versions[root]
  return v ? (v.list[v.sel] ?? root) : root
}

export function addVersion(root: string, key: string, kind: VersionKind = 'retry') {
  const v = state.versions[root] ?? { list: [root], sel: 0, kinds: [null] }
  const has = v.list.includes(key)
  const list = has ? v.list : [...v.list, key]
  const kinds = has ? (v.kinds ?? []) : [...(v.kinds ?? v.list.map(() => null)), kind]
  commit({ ...state, versions: { ...state.versions, [root]: { list, sel: list.indexOf(key), kinds } } })
}

/** 版本导航放哪：有编辑产生的版本 → 用户消息下；只有重试 → 回复操作条上 */
export function versionAnchor(v: Versions): 'user' | 'assistant' {
  return (v.kinds ?? []).includes('edit') ? 'user' : 'assistant'
}

export function selectVersion(root: string, index: number) {
  const v = state.versions[root]
  if (!v) return
  const sel = Math.max(0, Math.min(v.list.length - 1, index))
  if (sel === v.sel) return
  commit({ ...state, versions: { ...state.versions, [root]: { ...v, sel } } })
}

export function setFeedback(key: string, fb: Feedback | null) {
  const feedback = { ...state.feedback }
  if (fb) feedback[key] = { rating: fb.rating, note: fb.note?.slice(0, 2000) || undefined }
  else delete feedback[key]
  commit({ ...state, feedback })
}
