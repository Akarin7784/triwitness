import { useEffect, useRef } from 'react'
import { FolderGit2 } from 'lucide-react'
import type { ChatMessage } from '../types'
import { MessageBubble } from './MessageBubble'
import { Composer } from './Composer'
import { Tip } from './Tip'

interface ChatPanelProps {
  title: string
  project?: string
  messages: ChatMessage[]
  onSend: (text: string) => void
}

export function ChatPanel({ title, project, messages, onSend }: ChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length])

  return (
    <section className="flex min-w-0 flex-1 flex-col">
      <header className="flex items-center justify-between gap-4 px-8 pb-3 pt-5">
        <h2 className="min-w-0 truncate font-serif text-[20px] font-medium tracking-wide text-ink">{title}</h2>
        <div className="flex shrink-0 items-center gap-2">
          {project && (
            <Tip label="仓库" side="bottom">
              <span className="chip">
                <FolderGit2 size={11} strokeWidth={1.7} />
                {project}
              </span>
            </Tip>
          )}
          <Tip label="沙箱就绪" side="bottom">
            <span className="chip">
              <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-sage" />
              沙箱
            </span>
          </Tip>
        </div>
      </header>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto scroll-soft px-8 py-5">
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        <div ref={bottomRef} />
      </div>

      <Composer onSend={onSend} />
    </section>
  )
}
