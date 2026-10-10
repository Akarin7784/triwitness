import { motion } from 'framer-motion'
import { Boxes } from 'lucide-react'
import type { ArtifactKind } from '../lib/artifacts'
import { ArtifactIcon } from './ArtifactsPanel'

export interface ArtifactEntry {
  chat: string
  chatTitle: string
  artifact: string
  title: string
  kind: ArtifactKind
  time: string
}

/** 作品（照 Claude 的 Artifacts 页）：所有会话里产出的补丁 / PR 说明 / 代码，点开回到会话并打开作品栏 */
export function ArtifactsPage({ entries, onOpen }: { entries: ArtifactEntry[]; onOpen: (e: ArtifactEntry) => void }) {
  return (
    <main data-testid="artifacts-page" className="min-w-0 flex-1 overflow-y-auto scroll-soft">
      <div className="mx-auto max-w-[860px] px-12 py-10">
        <h1 className="font-serif text-[26px] text-ink">作品</h1>
        {entries.length === 0 ? (
          <div className="mt-16 flex flex-col items-center text-center">
            <Boxes size={28} strokeWidth={1.3} className="text-sepia-muted" />
            <p className="mt-3 font-serif text-[16px] text-ink">还没有作品</p>
            <p className="mt-1 max-w-[360px] text-[13px] leading-relaxed text-sepia-muted">任务产出的补丁、PR 说明和较长的代码会出现在这里。</p>
          </div>
        ) : (
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {entries.map((e, i) => (
              <motion.button
                key={`${e.chat}:${e.artifact}`}
                type="button"
                data-testid="artifact-entry"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ type: 'spring', stiffness: 420, damping: 34, delay: Math.min(i, 12) * 0.025 }}
                onClick={() => onOpen(e)}
                className="paper-card flex items-center gap-3 rounded-2xl px-4 py-3.5 text-left transition-[border-color,transform] duration-300 hover:-translate-y-0.5 hover:border-border"
              >
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-panel-raised text-sepia">
                  <ArtifactIcon kind={e.kind} size={17} />
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-[13.5px] text-ink">{e.title}</span>
                  <span className="block truncate text-[11.5px] text-sepia-muted">
                    {e.chatTitle} · {e.time}
                  </span>
                </span>
              </motion.button>
            ))}
          </div>
        )}
      </div>
    </main>
  )
}
