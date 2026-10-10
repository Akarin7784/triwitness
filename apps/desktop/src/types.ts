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

export type StreamTone = 'normal' | 'error' | 'warn' | 'chapter' | 'divider' | 'final'

export interface StreamLine {
  id: string
  role: RoleId
  text: string
  /** 视觉语气：失败赭红、警示琥珀、状态切换为章节标记、checkpoint 为细分隔线 */
  tone?: StreamTone
  /** 对应事件的 seq（事件驱动时） */
  seq?: number
  /** Optional delay before this line starts (ms) */
  pauseBefore?: number
}

export interface ActivitySession {
  id: string
  title: string
  subtitle: string
  lines: StreamLine[]
}
