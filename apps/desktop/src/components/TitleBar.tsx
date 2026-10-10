import { useEffect, useState } from 'react'
import { Feather, PanelLeft } from 'lucide-react'
import clsx from 'clsx'
import { appWindow, inTauri } from '../lib/appWindow'
import { Tip } from './Tip'

/**
 * 自绘标题栏（decorations: false）
 * - 整条带 data-tauri-drag-region：拖动移动窗口，双击最大化/还原（Tauri 内置）
 * - 装饰性子元素同样带该属性（或 pointer-events:none），保证点在字上也能拖
 * - 按钮不带该属性，可正常点击
 */
export function TitleBar({
  title,
  sidebarOpen,
  onToggleSidebar,
}: {
  title?: string
  sidebarOpen: boolean
  onToggleSidebar: () => void
}) {
  const [maximized, setMaximized] = useState(false)

  useEffect(() => {
    let off: (() => void) | undefined
    const sync = () => appWindow.isMaximized().then(setMaximized)
    sync()
    appWindow.onResized(sync).then((u) => (off = u))
    return () => off?.()
  }, [])

  return (
    <header
      data-tauri-drag-region
      className={clsx(
        'titlebar relative z-20 flex h-10 shrink-0 select-none items-center border-b border-border-soft/70',
        !inTauri && 'titlebar-preview',
      )}
    >
      <div data-tauri-drag-region className="flex h-full w-[248px] shrink-0 items-center gap-1 pl-3">
        <Tip label={sidebarOpen ? '收起侧栏' : '展开侧栏'} side="bottom">
          <button type="button" onClick={onToggleSidebar} className="tb-icon" aria-label="侧栏">
            <PanelLeft size={15} strokeWidth={1.5} />
          </button>
        </Tip>
        <span data-tauri-drag-region className="ml-1.5 flex items-center gap-2 text-ink">
          <Feather size={13} strokeWidth={1.6} className="pointer-events-none text-amber" />
          <span data-tauri-drag-region className="font-serif text-[14px] font-semibold tracking-[0.18em]">
            三证
          </span>
        </span>
      </div>

      <div data-tauri-drag-region className="flex h-full min-w-0 flex-1 items-center justify-center">
        {title && (
          <span data-tauri-drag-region className="truncate font-serif text-[12.5px] text-sepia">
            {title}
          </span>
        )}
      </div>

      <div className="flex h-full shrink-0 items-stretch">
        <WinButton label="最小化" onClick={appWindow.minimize}>
          <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden>
            <path d="M1 5.5h8" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
          </svg>
        </WinButton>
        <WinButton label={maximized ? '还原' : '最大化'} onClick={appWindow.toggleMaximize}>
          {maximized ? (
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden>
              <rect x="1" y="3" width="6" height="6" rx="1.2" stroke="currentColor" strokeWidth="1" />
              <path d="M3.2 3V2.2A1.2 1.2 0 0 1 4.4 1H7.8A1.2 1.2 0 0 1 9 2.2v3.4A1.2 1.2 0 0 1 7.8 6.8H7" stroke="currentColor" strokeWidth="1" />
            </svg>
          ) : (
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" aria-hidden>
              <rect x="1.2" y="1.2" width="7.6" height="7.6" rx="1.4" stroke="currentColor" strokeWidth="1" />
            </svg>
          )}
        </WinButton>
        <WinButton label="关闭" onClick={appWindow.close} danger>
          <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden>
            <path d="M1.5 1.5l7 7M8.5 1.5l-7 7" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
          </svg>
        </WinButton>
      </div>
    </header>
  )
}

function WinButton({
  label,
  onClick,
  danger,
  children,
}: {
  label: string
  onClick: () => void
  danger?: boolean
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className={clsx('win-btn', danger && 'win-btn-close')}
    >
      {children}
    </button>
  )
}
