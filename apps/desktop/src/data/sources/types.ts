import type { AnyEvent } from '../events'

export interface SubscribeOptions {
  /** 只推送 seq > afterSeq 的事件（续传；SSE 的 Last-Event-ID 语义） */
  afterSeq?: number
}

/** 事件数据源：fixture / mock / 以后的 SSE（UI-10）都实现这个接口 */
export interface EventSource {
  readonly id: string
  subscribe(onEvent: (e: AnyEvent) => void, opts?: SubscribeOptions): () => void
  /** 已推送的最大 seq；尚未推送为 -1 */
  readonly afterSeq: number
  close(): void
}
