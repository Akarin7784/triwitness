export type RoleId = 'planner' | 'executor' | 'verifier' | 'reviewer' | 'system' | 'user'

export interface Conversation {
  id: string
  title: string
  preview: string
  updatedAt: string
  project?: string
  active?: boolean
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  meta?: string
  timestamp: string
}

export interface StreamLine {
  id: string
  role: RoleId
  text: string
  /** Optional delay before this line starts (ms) */
  pauseBefore?: number
}

export interface ActivitySession {
  id: string
  title: string
  subtitle: string
  lines: StreamLine[]
}
