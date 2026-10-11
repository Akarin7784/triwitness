import { useState, type ReactNode } from 'react'
import {
  Boxes,
  CircleHelp,
  FolderClosed,
  Info,
  Keyboard,
  MessagesSquare,
  MoreHorizontal,
  PenLine,
  Pencil,
  Search,
  Settings,
  Star,
  StarOff,
  Trash2,
  FolderPlus,
  ChevronRight,
  FolderOpen,
} from 'lucide-react'
import { AnimatePresence, motion } from 'framer-motion'
import clsx from 'clsx'
import type { Phase } from '../data/mapEvent'
import { notYet } from '../lib/toast'
import { MenuDivider, MenuItem, Popover } from './Popover'
import { ProjectPicker } from './ProjectPicker'
import { Tip } from './Tip'
import { StatusGlyph } from './StatusGlyph'
import { t } from '../lib/i18n'

export interface SidebarItem {
  id: string
  title: string
  phase?: Phase
  label?: string
  time?: string
  starred?: boolean
  /** 所属项目 id */
  projectId?: string | null
  /** 最近活动时间（毫秒）：会话页按它排序 */
  at?: number
}

export type SidebarView = 'chat' | 'settings' | 'projects' | 'artifacts' | 'chats'

interface SidebarProps {
  items: SidebarItem[]
  activeId: string
  collapsed: boolean
  userName: string
  onSelect: (id: string) => void
  onNew: () => void
  onSearch: () => void
  /** 会话页（Claude 式完整列表）；搜索按钮打开 Ctrl+K 面板，两者不再是同一个入口（BUG4） */
  onChats: () => void
  onSettings: (section?: string) => void
  onShortcuts: () => void
  onRename: (id: string) => void
  onDelete: (id: string) => void
  onStar: (id: string) => void
  settingsActive?: boolean
  view: SidebarView
  onProjects: () => void
  onArtifacts: () => void
  onOpenProject: (id: string) => void
  projects: { id: string; name: string }[]
  onProject: (chat: string, project: string | null) => void
}

const SPRING = { type: 'spring', stiffness: 380, damping: 36, mass: 0.9 } as const

/**
 * Claude 式侧栏：新会话 · 搜索 · 会话 / 项目 / 作品入口 · 星标 · 近期（每项 … 菜单：星标 / 重命名 / 加入项目 / 删除）· 底部用户菜单。
 * 收起时变成图标窄栏（Ctrl+Shift+S），宽度弹簧过渡。
 */
export function Sidebar(p: SidebarProps) {
  const starred = p.items.filter((c) => c.starred)
  const inProject = (c: SidebarItem) => !!c.projectId && p.projects.some((x) => x.id === c.projectId)
  const recents = p.items.filter((c) => !c.starred && !inProject(c))
  const groups = p.projects
    .map((pr) => ({ ...pr, chats: p.items.filter((c) => !c.starred && c.projectId === pr.id) }))
    .filter((g) => g.chats.length > 0)
  return (
    <motion.aside
      data-testid="sidebar"
      data-collapsed={p.collapsed}
      initial={false}
      animate={{ width: p.collapsed ? 52 : 248 }}
      transition={SPRING}
      className="flex h-full shrink-0 flex-col overflow-hidden border-r border-border-soft bg-panel/70"
    >
      <div className={clsx('space-y-px pb-2 pt-3', p.collapsed ? 'px-2' : 'px-3')}>
        <NavButton collapsed={p.collapsed} icon={<PenLine size={15} strokeWidth={1.6} className="text-amber-ink" />} label={t('新会话')} kbd="Ctrl Shift O" onClick={p.onNew} testId="nav-new" />
        <NavButton collapsed={p.collapsed} icon={<Search size={15} strokeWidth={1.6} />} label={t('搜索')} kbd="Ctrl K" onClick={p.onSearch} testId="nav-search" />
        <NavButton collapsed={p.collapsed} icon={<MessagesSquare size={15} strokeWidth={1.6} />} label={t('会话')} onClick={p.onChats} testId="nav-chats" active={p.view === 'chats'} />
        <NavButton collapsed={p.collapsed} icon={<FolderClosed size={15} strokeWidth={1.6} />} label={t('项目')} onClick={p.onProjects} testId="nav-projects" active={p.view === 'projects'} />
        <NavButton collapsed={p.collapsed} icon={<Boxes size={15} strokeWidth={1.6} />} label={t('作品')} onClick={p.onArtifacts} testId="nav-artifacts" active={p.view === 'artifacts'} />
      </div>

      <AnimatePresence initial={false}>
        {!p.collapsed && (
          <motion.nav
            key="list"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1, transition: { delay: 0.08, duration: 0.2 } }}
            exit={{ opacity: 0, transition: { duration: 0.1 } }}
            className="min-h-0 w-[248px] flex-1 overflow-y-auto scroll-soft px-2 pb-4"
          >
            {starred.length > 0 && (
              <>
                <SectionLabel>{t('星标')}</SectionLabel>
                <div className="space-y-px">
                  {starred.map((c) => (
                    <ChatRow key={c.id} c={c} {...p} />
                  ))}
                </div>
              </>
            )}
            {groups.length > 0 && (
              <>
                <SectionLabel>{t('项目')}</SectionLabel>
                {groups.map((g) => (
                  <ProjectGroup key={g.id} name={g.name} onOpen={() => p.onOpenProject(g.id)} defaultOpen={g.chats.some((c) => c.id === p.activeId)}>
                    {g.chats.map((c) => (
                      <ChatRow key={c.id} c={c} {...p} nested />
                    ))}
                  </ProjectGroup>
                ))}
              </>
            )}
            <SectionLabel>{t('近期')}</SectionLabel>
            {/* 不用 framer layout：长列表里只动 transform / opacity（SUGG2：悬停不再抖） */}
            <div className="space-y-px">
              <AnimatePresence initial={false}>
                {recents.map((c) => (
                  <ChatRow key={c.id} c={c} {...p} />
                ))}
              </AnimatePresence>
            </div>
          </motion.nav>
        )}
      </AnimatePresence>
      {p.collapsed && <div className="flex-1" />}

      <UserMenu {...p} />
    </motion.aside>
  )
}

function SectionLabel({ children }: { children: ReactNode }) {
  return <p className="px-4 pb-1.5 pt-4 text-[10.5px] tracking-[0.14em] text-sepia-muted">{children}</p>
}

function ProjectGroup({ name, onOpen, defaultOpen, children }: { name: string; onOpen: () => void; defaultOpen: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div data-testid="project-group">
      <div className="group flex items-center rounded-lg pr-1.5 transition-colors duration-300 hover:bg-panel-raised/60">
        <button
          type="button"
          aria-expanded={open}
          aria-label={open ? t('收起 {0}', name) : t('展开 {0}', name)}
          onClick={() => setOpen((o) => !o)}
          className="flex h-8 w-7 shrink-0 items-center justify-center pl-2 text-sepia-muted"
        >
          <ChevronRight size={12} strokeWidth={1.8} className={clsx('transition-transform duration-300', open && 'rotate-90')} />
        </button>
        <button type="button" onClick={onOpen} className="flex min-w-0 flex-1 items-center gap-1.5 py-1.5 text-left text-[12.5px] text-ink-soft">
          {open ? <FolderOpen size={13} strokeWidth={1.6} className="shrink-0 text-amber-ink" /> : <FolderClosed size={13} strokeWidth={1.6} className="shrink-0 text-sepia" />}
          <span className="truncate">{name}</span>
        </button>
      </div>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={SPRING}
            className="space-y-px overflow-hidden"
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function NavButton({
  collapsed,
  icon,
  label,
  kbd,
  onClick,
  testId,
  active,
}: {
  collapsed: boolean
  icon: ReactNode
  label: string
  kbd?: string
  onClick: () => void
  testId?: string
  active?: boolean
}) {
  const btn = (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      data-testid={testId}
      className={clsx(
        'group flex h-9 items-center gap-2.5 rounded-xl text-[13px] text-ink-soft transition-colors duration-300 hover:bg-panel-raised',
        collapsed ? 'w-9 justify-center' : 'w-full px-3',
        active && 'bg-panel-raised text-ink',
      )}
      aria-current={active ? 'page' : undefined}
    >
      <span className="flex w-4 shrink-0 justify-center">{icon}</span>
      {!collapsed && (
        <>
          <span className="truncate">{label}</span>
          {kbd && (
            <span className="ml-auto font-mono text-[10px] text-sepia-muted opacity-0 transition-opacity duration-300 group-hover:opacity-100">
              {kbd}
            </span>
          )}
        </>
      )}
    </button>
  )
  return collapsed ? (
    <Tip label={kbd ? `${label} · ${kbd}` : label} side="right">
      {btn}
    </Tip>
  ) : (
    btn
  )
}

function ChatRow({
  c,
  activeId,
  settingsActive,
  onSelect,
  onRename,
  onDelete,
  onStar,
  view,
  projects,
  onProject,
  nested,
}: { c: SidebarItem; nested?: boolean } & SidebarProps) {
  const [menu, setMenu] = useState(false)
  const [page, setPage] = useState<'main' | 'project'>('main')
  const closeMenu = () => {
    setMenu(false)
    window.setTimeout(() => setPage('main'), 200)
  }
  const active = !settingsActive && view === 'chat' && c.id === activeId
  return (
    <motion.div
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -6, pointerEvents: 'none', transition: { duration: 0.16 } }}
      transition={SPRING}
      className="relative"
    >
      <div
        role="button"
        tabIndex={0}
        data-testid="chat-row"
        data-id={c.id}
        onClick={() => onSelect(c.id)}
        onKeyDown={(e) => e.key === 'Enter' && onSelect(c.id)}
        className={clsx(
          nested ? 'pl-8' : 'pl-4',
          // SUGG2：固定行高；悬停只改背景，时间与 ⋯ 共用一个固定宽度的槽位（交叉淡入，不改布局）
          'group flex h-8 w-full cursor-default items-center gap-2 rounded-lg pr-1 text-left outline-none transition-colors duration-300 focus-visible:ring-1 focus-visible:ring-amber/40',
          active || menu ? 'bg-panel-raised shadow-[0_1px_0_color-mix(in_srgb,var(--color-border)_60%,transparent)]' : 'hover:bg-panel-raised/60',
        )}
      >
        {c.phase && (
          <Tip label={c.label ?? ''} side="right">
            <span className="flex h-4 w-3.5 items-center justify-center">
              <StatusGlyph phase={c.phase} />
            </span>
          </Tip>
        )}
        <span className={clsx('min-w-0 flex-1 truncate font-serif text-[13px]', active ? 'text-ink' : 'text-ink-soft/90')}>
          {c.title}
        </span>
        <span data-testid="chat-row-slot" className="relative flex h-6 w-[38px] shrink-0 items-center justify-end">
          {c.time && (
            <span
              className={clsx(
                'pointer-events-none whitespace-nowrap pr-1 font-mono text-[10px] tabular-nums text-sepia-muted transition-opacity duration-200 group-hover:opacity-0 group-focus-visible:opacity-0 group-has-[:focus-visible]:opacity-0',
                menu && 'opacity-0',
              )}
            >
              {c.time}
            </span>
          )}
          <button
            type="button"
            aria-label={t('更多')}
            data-testid="chat-more"
            aria-haspopup="menu"
            aria-expanded={menu}
            onClick={(e) => {
              e.stopPropagation()
              if (menu) closeMenu()
              else setMenu(true)
            }}
            className={clsx(
              'absolute right-0 top-0 inline-flex h-6 w-6 items-center justify-center rounded-md text-sepia transition-[opacity,background-color,color] duration-200 hover:bg-parchment-deep hover:text-ink focus-visible:opacity-100',
              menu ? 'opacity-100' : 'pointer-events-none opacity-0 group-hover:pointer-events-auto group-hover:opacity-100 group-focus-visible:opacity-100 group-has-[:focus-visible]:opacity-100',
            )}
          >
            <MoreHorizontal size={14} strokeWidth={1.7} />
          </button>
        </span>
      </div>
      <Popover open={menu} onClose={closeMenu} side="down" align="right" className="w-[196px]" testId="chat-menu">
        {page === 'main' ? (
          <>
            <MenuItem icon={c.starred ? StarOff : Star} label={c.starred ? t('取消星标') : t('星标')} onClick={() => (closeMenu(), onStar(c.id))} />
            <MenuItem icon={Pencil} label={t('重命名')} onClick={() => (closeMenu(), onRename(c.id))} testId="menu-rename" />
            <MenuItem icon={FolderPlus} label={c.projectId ? t('更换项目') : t('加入项目')} onClick={() => setPage('project')} testId="menu-project" />
            <MenuDivider />
            <MenuItem icon={Trash2} label={t('删除')} danger onClick={() => (closeMenu(), onDelete(c.id))} testId="menu-delete" />
          </>
        ) : (
          <ProjectPicker
            menu={{ projects, projectId: c.projectId ?? null, onProject: (pid) => onProject(c.id, pid) }}
            onBack={() => setPage('main')}
            onDone={closeMenu}
          />
        )}
      </Popover>
    </motion.div>
  )
}

function UserMenu({ collapsed, userName, onSettings, onShortcuts, settingsActive }: SidebarProps) {
  const [open, setOpen] = useState(false)
  const name = userName.trim() || t('本机')
  return (
    <div className="relative border-t border-border-soft/80 p-2">
      <button
        type="button"
        data-testid="user-menu"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t('用户菜单')}
        onClick={() => setOpen((o) => !o)}
        className={clsx(
          'flex h-10 items-center gap-2.5 rounded-lg text-[12.5px] transition-colors duration-300 hover:bg-panel-raised',
          collapsed ? 'w-9 justify-center' : 'w-full px-2.5',
          (open || settingsActive) && 'bg-panel-raised',
        )}
      >
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-espresso font-serif text-[12px] text-parchment">
          {name.slice(0, 1)}
        </span>
        {!collapsed && <span className="truncate text-ink-soft">{name}</span>}
      </button>
      <Popover open={open} onClose={() => setOpen(false)} className="w-[220px]" testId="user-popover">
        <MenuItem icon={Settings} label={t('设置')} kbd="Ctrl ," onClick={() => (setOpen(false), onSettings())} testId="open-settings" />
        <MenuItem icon={Keyboard} label={t('快捷键')} kbd="Ctrl /" onClick={() => (setOpen(false), onShortcuts())} />
        <MenuItem icon={CircleHelp} label={t('帮助')} onClick={() => (setOpen(false), notYet(t('帮助')))} />
        <MenuDivider />
        <MenuItem icon={Info} label={t('关于三证')} onClick={() => (setOpen(false), onSettings('about'))} />
      </Popover>
    </div>
  )
}
