import { WritingStream } from './WritingStream'
import type { RoleId, StreamLine } from '../types'

interface ActivityPanelProps {
  title: string
  lines: StreamLine[]
  activeRole: RoleId | null
  onRestart: () => void
  onReveal: (line: StreamLine | null) => void
  sessionKey?: string
  onDone?: (done: boolean) => void
}

export function ActivityPanel({ title, lines, activeRole, onRestart, onReveal, sessionKey, onDone }: ActivityPanelProps) {
  return (
    <aside className="flex h-full w-[392px] shrink-0 flex-col border-l border-border-soft bg-panel/60">
      <WritingStream
        lines={lines}
        title={title}
        activeRole={activeRole}
        onRestart={onRestart}
        onReveal={onReveal}
        sessionKey={sessionKey}
        onDone={onDone}
      />
    </aside>
  )
}
