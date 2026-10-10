/**
 * 项目（UI-21 第 3 轮，照 Claude Projects）：名称、说明（自定义指令）、知识文件；会话归属到项目。
 * 知识文件已落盘到 ~/.triwitness/attachments/（attach_save），这里只记路径与大小。
 * 起任务时：项目说明进“用户设置”，知识文件作为附件一起交给核心。localStorage 持久化，可订阅。
 */
import { useSyncExternalStore } from 'react'
import { t } from './i18n'

export interface KnowledgeFile {
  name: string
  path: string
  size: number
}
export interface Project {
  id: string
  name: string
  description: string
  instructions: string
  knowledge: KnowledgeFile[]
  createdAt: number
  updatedAt: number
}
interface State {
  projects: Project[]
  /** 会话根 key → 项目 id */
  chats: Record<string, string>
}

const KEY = 'tw.projects'
export const MAX_KNOWLEDGE = 20

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
    const projects = Array.isArray(v.projects) ? v.projects.filter((p) => p && typeof p.id === 'string') : []
    return { projects, chats: v.chats && typeof v.chats === 'object' ? v.chats : {} }
  } catch {
    return { projects: [], chats: {} }
  }
}

let state: State = load()
const subs = new Set<() => void>()
function commit(next: State) {
  state = next
  storage()?.setItem(KEY, JSON.stringify(next))
  for (const s of subs) s()
}

export function getProjects(): State {
  return state
}
export function reloadProjects() {
  state = load()
}
export function useProjects(): State {
  return useSyncExternalStore(
    (fn) => {
      subs.add(fn)
      return () => subs.delete(fn)
    },
    () => state,
  )
}

export function createProject(name: string, description = ''): Project {
  const now = Date.now()
  const p: Project = {
    id: `p${now.toString(36)}${Math.random().toString(36).slice(2, 6)}`,
    name: name.trim().slice(0, 60) || t('未命名项目'),
    description: description.trim().slice(0, 300),
    instructions: '',
    knowledge: [],
    createdAt: now,
    updatedAt: now,
  }
  commit({ ...state, projects: [p, ...state.projects] })
  return p
}

export function updateProject(id: string, patch: Partial<Pick<Project, 'name' | 'description' | 'instructions'>>) {
  const clean = { ...patch }
  if (clean.name !== undefined) clean.name = clean.name.trim().slice(0, 60) || t('未命名项目')
  if (clean.description !== undefined) clean.description = clean.description.slice(0, 300)
  if (clean.instructions !== undefined) clean.instructions = clean.instructions.slice(0, 4000)
  commit({
    ...state,
    projects: state.projects.map((p) => (p.id === id ? { ...p, ...clean, updatedAt: Date.now() } : p)),
  })
}

export function deleteProject(id: string) {
  const chats = Object.fromEntries(Object.entries(state.chats).filter(([, pid]) => pid !== id))
  commit({ projects: state.projects.filter((p) => p.id !== id), chats })
}

export function addKnowledge(id: string, files: KnowledgeFile[]) {
  commit({
    ...state,
    projects: state.projects.map((p) => {
      if (p.id !== id) return p
      const names = new Set(files.map((f) => f.name))
      const knowledge = [...p.knowledge.filter((k) => !names.has(k.name)), ...files].slice(-MAX_KNOWLEDGE)
      return { ...p, knowledge, updatedAt: Date.now() }
    }),
  })
}

export function removeKnowledge(id: string, path: string) {
  commit({
    ...state,
    projects: state.projects.map((p) => (p.id === id ? { ...p, knowledge: p.knowledge.filter((k) => k.path !== path) } : p)),
  })
}

/** 归到项目；pid=null 移出项目 */
export function setChatProject(chat: string, pid: string | null) {
  const chats = { ...state.chats }
  if (pid && state.projects.some((p) => p.id === pid)) chats[chat] = pid
  else delete chats[chat]
  commit({ ...state, chats })
}

/** 新会话（local:）起任务后变成 live: key：项目归属跟过去 */
export function moveChat(from: string, to: string) {
  const pid = state.chats[from]
  if (!pid) return
  const chats = { ...state.chats, [to]: pid }
  delete chats[from]
  commit({ ...state, chats })
}

export function projectOf(chat: string, s: State = state): Project | undefined {
  const pid = s.chats[chat]
  return pid ? s.projects.find((p) => p.id === pid) : undefined
}
