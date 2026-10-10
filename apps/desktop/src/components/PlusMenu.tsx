import { Camera, Globe, Palette, Paperclip, Plug, Puzzle, Sparkles, Telescope, Plus } from 'lucide-react'
import clsx from 'clsx'
import { notYet } from '../lib/toast'
import { Kbd, MenuDivider, Popover } from './Popover'
import { Tip } from './Tip'

const ITEMS = [
  { icon: Paperclip, label: '添加文件或图片', kbd: 'Ctrl U' },
  { icon: Camera, label: '截图' },
  null,
  { icon: Globe, label: '网页搜索' },
  { icon: Telescope, label: '深度研究' },
  null,
  { icon: Sparkles, label: '技能' },
  { icon: Plug, label: '连接器' },
  { icon: Puzzle, label: '插件' },
  null,
  { icon: Palette, label: '风格' },
] as const

/** 输入框左下角的 +：与 Claude 同一组入口；未实现的点了给一句“即将推出” */
export function PlusMenu({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  return (
    <div className="relative">
      <Tip label="添加" side="top-start">
        <button
          type="button"
          aria-label="添加"
          data-testid="plus-button"
          onClick={() => onOpenChange(!open)}
          className={clsx(
            'inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border-soft text-sepia transition-all duration-300 hover:border-border hover:text-amber',
            open && 'border-border bg-panel-raised text-amber',
          )}
        >
          <Plus size={15} strokeWidth={1.7} className={clsx('transition-transform duration-300', open && 'rotate-45')} />
        </button>
      </Tip>
      <Popover open={open} onClose={() => onOpenChange(false)} className="w-[228px]" testId="plus-menu">
        {ITEMS.map((it, i) =>
          it === null ? (
            <MenuDivider key={i} />
          ) : (
            <button
              key={it.label}
              type="button"
              className="menu-item"
              onClick={() => {
                onOpenChange(false)
                notYet(it.label)
              }}
            >
              <it.icon size={14} strokeWidth={1.6} className="text-sepia" />
              <span>{it.label}</span>
              {'kbd' in it && <Kbd>{it.kbd}</Kbd>}
            </button>
          ),
        )}
      </Popover>
    </div>
  )
}
