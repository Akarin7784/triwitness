import { createContext, type RefObject } from 'react'

/** 对话滚动容器（ChatPanel 提供）：虚拟列表据此算可见窗口 */
export const ChatScrollContext = createContext<RefObject<HTMLElement | null> | null>(null)
