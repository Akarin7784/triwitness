import { useRef, useState } from 'react'
import clsx from 'clsx'
import { ChevronDown, FolderGit2, FolderOpen, X } from 'lucide-react'
import { forgetRecentRepo, recentRepos, rememberRepo } from '../bridge/liveStore'
import { baseName, pickFolder } from '../lib/pickFolder'
import { t as tr } from '../lib/i18n'
import { toast } from '../lib/toast'
import { MenuDivider, Popover } from './Popover'
import { Tip } from './Tip'

export interface ComposerRepo {
  value: string
  onChange: (v: string) => void
  placeholder: string
}

/**
 * 仓库选择（BUG2）：chip 只显示文件夹名、永不换行（省略号），完整路径在提示里；
 * 点开：选择文件夹（原生对话框）· 最近用过 · 手动输入。chip 不再原地变成输入框，所以旁边的模型选择器不会被挤换行。
 */
export function RepoPicker({ repo, open, onOpenChange }: { repo: ComposerRepo; open: boolean; onOpenChange: (o: boolean) => void }) {
  const [recent, setRecent] = useState<string[]>([])
  const [manual, setManual] = useState('')
  const input = useRef<HTMLInputElement>(null)
  // 每次打开时刷新“最近”与输入框（渲染期按 open 变化调整状态，不用 effect）
  const [wasOpen, setWasOpen] = useState(open)
  if (open !== wasOpen) {
    setWasOpen(open)
    if (open) {
      setRecent(recentRepos())
      setManual(repo.value)
    }
  }
  const choose = (p: string) => {
    const v = p.trim()
    if (!v) return
    repo.onChange(v)
    rememberRepo(v)
    onOpenChange(false)
  }
  const browse = async () => {
    try {
      const r = await pickFolder(repo.value)
      if (r === undefined) {
        toast(tr('这里没有系统文件夹对话框，请在下面输入路径'))
        input.current?.focus()
        return
      }
      if (r) choose(r)
    } catch (e) {
      toast(tr('打开文件夹对话框失败：{0}', String(e)))
    }
  }
  const label = repo.value ? baseName(repo.value) : repo.placeholder
  return (
    <div className="relative min-w-[84px] shrink">
      <Tip label={<span className="font-mono">{repo.value || tr('仓库路径')}</span>} side="top-start" className="min-w-0 max-w-full">
        <button
          type="button"
          data-testid="repo-chip"
          aria-haspopup="menu"
          aria-expanded={open}
          aria-label={tr('仓库路径')}
          onClick={() => onOpenChange(!open)}
          className={clsx('chip min-w-0 max-w-[220px] transition-colors duration-300 hover:text-amber-ink', open && 'text-amber-ink')}
        >
          <FolderGit2 size={11} strokeWidth={1.7} className="shrink-0" />
          <span className="min-w-0 truncate font-mono text-[11.5px]">{label}</span>
          <ChevronDown size={11} strokeWidth={1.7} className={clsx('shrink-0 transition-transform duration-300', open && 'rotate-180')} />
        </button>
      </Tip>
      <Popover open={open} onClose={() => onOpenChange(false)} className="w-[340px]" testId="repo-menu">
        <button type="button" role="menuitem" data-testid="repo-browse" onClick={() => void browse()} className="menu-item">
          <FolderOpen size={14} strokeWidth={1.6} className="text-sepia" />
          <span>{tr('选择文件夹…')}</span>
        </button>
        {recent.length > 0 && (
          <>
            <MenuDivider />
            <p className="px-3 pb-1 pt-1.5 text-[11px] text-sepia-muted">{tr('最近')}</p>
            <ul data-testid="repo-recent">
              {recent.map((r) => (
                <li key={r} className="group/recent relative">
                  <button type="button" role="menuitemradio" aria-checked={r === repo.value} onClick={() => choose(r)} className="menu-item pr-8">
                    <FolderGit2 size={14} strokeWidth={1.6} className="shrink-0 text-sepia" />
                    <span className="flex min-w-0 flex-1 flex-col">
                      <span className="truncate text-ink">{baseName(r)}</span>
                      <span className="truncate font-mono text-[10.5px] text-sepia-muted">{r}</span>
                    </span>
                  </button>
                  <button
                    type="button"
                    aria-label={tr('从最近列表移除')}
                    onClick={() => (forgetRecentRepo(r), setRecent(recentRepos()))}
                    className="absolute right-2 top-1/2 hidden h-6 w-6 -translate-y-1/2 items-center justify-center rounded-md text-sepia-muted hover:bg-parchment-deep hover:text-ink group-hover/recent:inline-flex"
                  >
                    <X size={12} strokeWidth={1.8} />
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
        <MenuDivider />
        <form
          className="flex items-center gap-1.5 px-1.5 pb-1 pt-1"
          onSubmit={(e) => {
            e.preventDefault()
            choose(manual)
          }}
        >
          <input
            ref={input}
            data-testid="repo-manual"
            value={manual}
            onChange={(e) => setManual(e.target.value)}
            placeholder={repo.placeholder}
            spellCheck={false}
            aria-label={tr('输入仓库路径')}
            className="min-w-0 flex-1 rounded-md border border-border-soft bg-transparent px-2 py-1 font-mono text-[11.5px] text-ink outline-none placeholder:text-sepia-muted/70 focus:border-amber/60"
          />
          <button type="submit" className="shrink-0 whitespace-nowrap rounded-md px-2 py-1 text-[12px] text-ink-soft hover:bg-panel-raised">
            {tr('使用')}
          </button>
        </form>
      </Popover>
    </div>
  )
}
