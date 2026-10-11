import clsx from 'clsx'
import type { ChatMessage } from '../types'
import { Tip } from './Tip'

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'
  return (
    <article className={clsx('cv-auto group max-w-[720px] fade-in', isUser ? 'ml-auto' : 'mr-auto')}>
      <div
        className={clsx(
          'rounded-2xl px-4 py-3.5',
          isUser ? 'bg-ink text-parchment shadow-md' : 'paper-card text-ink-soft',
        )}
      >
        <p className="selectable whitespace-pre-wrap text-[14px] leading-[1.8]">
          {message.content.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
            part.startsWith('**') && part.endsWith('**') ? (
              <strong key={i} className="font-medium text-inherit">
                {part.slice(2, -2)}
              </strong>
            ) : (
              <span key={i}>{part}</span>
            ),
          )}
        </p>
      </div>
      <div
        className={clsx(
          'mt-1 flex h-4 px-1 text-[10px] text-sepia-muted opacity-0 transition-opacity duration-500 group-hover:opacity-100',
          isUser && 'justify-end',
        )}
      >
        {message.meta ? (
          <Tip label={message.meta} side={isUser ? 'top-end' : 'top-start'}>
            <span className="tabular-nums">{message.timestamp}</span>
          </Tip>
        ) : (
          <span className="tabular-nums">{message.timestamp}</span>
        )}
      </div>
    </article>
  )
}
