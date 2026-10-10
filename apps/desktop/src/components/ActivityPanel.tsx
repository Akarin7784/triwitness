import { WritingStream } from './WritingStream'
import type { ActivitySession } from '../types'
import { useMockFeed } from '../hooks/useMockFeed'

export function ActivityPanel({ session }: { session: ActivitySession }) {
  const feed = useMockFeed(session.lines)
  return (
    <aside className="flex h-full w-[392px] shrink-0 flex-col border-l border-border-soft bg-panel/60">
      <WritingStream lines={feed.lines} onRestart={feed.restart} title={session.title} />
    </aside>
  )
}
