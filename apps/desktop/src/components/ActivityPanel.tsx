import { WritingStream } from './WritingStream'
import type { RoleId, StreamLine } from '../types'

interface ActivityPanelProps {
  title: string
  lines: StreamLine[]
  activeRole: RoleId | null
  onRestart: () => void
  onReveal: (line: StreamLine | null) => void
}

export function ActivityPanel({ title, lines, activeRole, onRestart, onReveal }: ActivityPanelProps) {
  return (
    <aside className="flex h-full w-[392px] shrink-0 flex-col border-l border-border-soft bg-panel/60">
      <WritingStream
        lines={lines}
        title={title}
        activeRole={activeRole}
        onRestart={onRestart}
        onReveal={onReveal}
      />
    </aside>
  )
}
