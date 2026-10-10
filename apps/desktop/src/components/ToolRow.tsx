import { useState } from 'react'
import {
  ChevronRight,
  FilePen,
  FilePlus2,
  FileSearch,
  Flag,
  FlaskConical,
  ShieldCheck,
  SquareTerminal,
  Wrench,
  type LucideIcon,
} from 'lucide-react'
import clsx from 'clsx'
import { toolTitle, type ToolBlock } from '../data/turns'

const ICON: Record<string, LucideIcon> = {
  read_file: FileSearch,
  list_files: FileSearch,
  grep: FileSearch,
  write_file: FilePlus2,
  edit_file: FilePen,
  run_tests: FlaskConical,
  submit_repro: ShieldCheck,
  bash: SquareTerminal,
  powershell: SquareTerminal,
  finish: Flag,
}

function secs(ms: number) {
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(ms < 10_000 ? 1 : 0)}s`
}

/** Claude 式工具行：一行小字（图标 · 动作 · 耗时），点开看参数与输出 */
export function ToolRow({ block }: { block: ToolBlock }) {
  const [open, setOpen] = useState(false)
  const Icon = ICON[block.tool] ?? Wrench
  const detail = !!(block.args || block.output)
  return (
    <div data-testid="tool-row" className="fade-in">
      <button
        type="button"
        onClick={() => detail && setOpen((o) => !o)}
        className={clsx(
          'group flex w-full max-w-full items-center gap-2 rounded-lg px-2 py-1 text-left text-[12.5px] transition-colors duration-300',
          detail ? 'hover:bg-panel-raised/80' : 'cursor-default',
          open && 'bg-panel-raised/80',
        )}
      >
        <Icon size={13} strokeWidth={1.6} className={block.ok ? 'shrink-0 text-sepia' : 'shrink-0 text-rose-ink'} />
        <span className={clsx('min-w-0 flex-1 truncate font-mono text-[12px]', block.ok ? 'text-ink-soft' : 'text-rose-ink')}>
          {toolTitle(block)}
        </span>
        <span className="shrink-0 tabular-nums text-[10.5px] text-sepia-muted">{secs(block.durationMs)}</span>
        {detail && (
          <ChevronRight
            size={12}
            strokeWidth={1.7}
            className={clsx('shrink-0 text-sepia-muted transition-transform duration-300', open && 'rotate-90')}
          />
        )}
      </button>
      {open && (
        <div className="fade-in mb-1.5 ml-7 mr-1 mt-0.5 space-y-1.5">
          {block.args && <pre className="tool-pre selectable">{block.args}</pre>}
          {block.output && <pre className="tool-pre selectable max-h-56">{block.output}</pre>}
          {block.permission && <p className="text-[10.5px] text-sepia-muted">权限 · {block.permission}</p>}
        </div>
      )}
    </div>
  )
}
