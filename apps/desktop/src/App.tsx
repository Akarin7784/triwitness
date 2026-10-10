import { useEffect, useEffectEvent, useMemo, useState } from 'react'
import { Sidebar, type SidebarItem } from './components/Sidebar'
import { ChatPanel } from './components/ChatPanel'
import { ActivityPanel } from './components/ActivityPanel'
import { StatusBar } from './components/StatusBar'
import { SettingsPage, type SettingsSection } from './components/SettingsPage'
import { ConfirmDeleteDialog, RenameDialog, SearchPalette, ShortcutsDialog } from './components/ChatDialogs'
import { TitleBar } from './components/TitleBar'
import { ContextMenu } from './components/ContextMenu'
import { useEventFeed } from './hooks/useEventFeed'
import { useFixtureCatalog } from './hooks/useFixtureCatalog'
import { FIXTURES, FixtureSource, type FixtureName } from './data/sources/fixture'
import { createMockSource } from './data/sources/mock'
import { foldRun } from './data/mapEvent'
import { foldTurn } from './data/turns'
import { getPrefs, setPrefs, takeUnrestricted, usePrefs, type Prefs } from './lib/prefs'
import {
  addVersion,
  currentVersion,
  deleteChat,
  isVersionChild,
  renameChat,
  selectVersion,
  setFeedback,
  toggleStar,
  useChats,
  versionAnchor,
  type VersionKind,
} from './lib/chats'
import { matchShortcut } from './lib/shortcuts'
import { dialogOpen } from './lib/dialogState'
import { notYet, toast } from './lib/toast'
import { UNRESTRICTED_PHRASE, type RunChoices } from './bridge/choices'
import { Toaster } from './components/Toaster'
import { MotionConfig } from 'framer-motion'
import { parseSourceParam, speedParam, writeSourceParam, type SourceKey } from './lib/sourceParam'
import type { ChatMessage, StreamLine } from './types'
import type { Phase } from './data/mapEvent'
import type { TaskMeta } from './bridge/liveTask'
import {
  approve,
  cancelTask,
  coreMode,
  forgetTask,
  lastRepo,
  liveTaskFor,
  startTask,
  useCoreAvailable,
  useLiveSnapshot,
  useLiveTask,
  useTaskMetas,
} from './bridge/liveStore'

/** 真实任务尚未注册（续上中）时的占位 key，注册后换成真 key 触发重新订阅 */
const PENDING = '#pending'

function makeSource(key: string) {
  if (key.endsWith(PENDING)) return null
  if (key.startsWith('live:')) return liveTaskFor(key.slice('live:'.length))
  const speed = speedParam(window.location.search)
  if (key === 'mock') return createMockSource({ speed })
  if (key.startsWith('fixture:')) {
    const name = key.slice('fixture:'.length) as FixtureName
    return new FixtureSource(name, FIXTURES[name], { speed })
  }
  return null
}

function livePhase(m: TaskMeta): Phase {
  if (!m.status) return 'active'
  if (m.status === 'done') return m.verdict && m.verdict !== 'pass' ? 'waiting' : 'done'
  if (m.status === 'cancelled') return 'cancelled'
  if (m.status === 'budget_exceeded') return 'budget'
  return 'failed'
}

const LIVE_LABEL: Record<string, string> = {
  done: '已完成',
  failed: '未完成',
  stuck: '卡住',
  budget_exceeded: '超预算',
  cancelled: '已停止',
  error: '出错',
}

/** 设置 → 本次任务的选择；勇士模式“上膛”时只给这一个任务 */
function runChoices(p: Prefs, mode: string, warrior: boolean): RunChoices {
  return {
    model: p.model,
    thinking: p.thinking,
    backend: p.backend,
    maxCost: p.maxCost,
    permissionMode: warrior ? 'unrestricted' : p.permissionMode,
    confirmUnrestricted: warrior ? UNRESTRICTED_PHRASE : undefined,
    allowPeak: mode === 'live' && p.allowPeak,
  }
}

/** 主题 / 对话字体 / 字号 → 根元素（自动主题跟随系统） */
function useAppearance(p: Prefs) {
  useEffect(() => {
    const root = document.documentElement
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)')
    const apply = () => {
      root.dataset.theme = p.theme === 'auto' ? (mq?.matches ? 'dark' : 'light') : p.theme
    }
    apply()
    root.dataset.chatFont = p.chatFont
    root.style.setProperty('--chat-scale', String(p.fontScale))
    if (p.theme !== 'auto' || !mq) return
    mq.addEventListener('change', apply)
    return () => mq.removeEventListener('change', apply)
  }, [p.theme, p.chatFont, p.fontScale])
}

function clock() {
  const d = new Date()
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export default function App() {
  const catalog = useFixtureCatalog()
  const prefs = usePrefs()
  const chats = useChats()
  useAppearance(prefs)
  /** source = 会话根 key；display = 当前显示的版本（重试 / 编辑产生的新任务） */
  const [source, setSource] = useState<SourceKey>(() => parseSourceParam(window.location.search))
  const display = currentVersion(source, chats) as SourceKey
  const [locals, setLocals] = useState<{ id: SourceKey; title: string }[]>([])
  const [localMessages, setLocalMessages] = useState<Record<string, ChatMessage[]>>({})
  // 右侧推流写到哪一行（按显示的版本分开记，切版本自动从头）
  const [reveal, setReveal] = useState<{ key: string; seq: number }>({ key: '', seq: -1 })
  const params = new URLSearchParams(window.location.search)
  const [view, setView] = useState<'chat' | 'settings'>(() => (params.get('view') === 'settings' ? 'settings' : 'chat'))
  const [section, setSection] = useState<SettingsSection>(() => (params.get('section') as SettingsSection) || 'general')
  const [palette, setPalette] = useState(false)
  const [shortcuts, setShortcuts] = useState(false)
  const [renaming, setRenaming] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [warriorTasks, setWarriorTasks] = useState<Set<string>>(() => new Set())

  const coreOk = useCoreAvailable()
  const metas = useTaskMetas()
  const liveId = display.startsWith('live:') ? display.slice('live:'.length) : null
  const liveTask = useLiveTask(liveId)
  const snap = useLiveSnapshot(liveTask)
  const [repo, setRepo] = useState(() => (coreMode() === 'demo' ? '' : lastRepo()))
  const [startErr, setStartErr] = useState<string | null>(null)

  const revealedSeq = reveal.key === display ? reveal.seq : -1
  const feed = useEventFeed(liveId && !liveTask ? `${display}${PENDING}` : display, makeSource)

  // 右侧书写推流的角色点跟笔；对话流（Claude 式）与顶部状态 / 费用签按事件实时走
  const run = useMemo(() => foldRun(feed.events, revealedSeq), [feed.events, revealedSeq])
  const live = useMemo(() => foldRun(feed.events), [feed.events])
  const turn = useMemo(() => foldTurn(feed.events), [feed.events])

  const select = (key: SourceKey) => {
    setSource(key)
    writeSourceParam(key)
    setView('chat')
  }

  const onReveal = (line: StreamLine | null) => setReveal({ key: display, seq: line?.seq ?? -1 })
  const onRestart = () => {
    setReveal({ key: display, seq: -1 })
    feed.restart()
  }

  const items: SidebarItem[] = useMemo(() => {
    const all: SidebarItem[] = [
      ...locals.map((l) => ({ id: l.id, title: l.title })),
      ...metas.map((m) => ({
        id: `live:${m.id}` as SourceKey,
        title: m.title,
        phase: livePhase(m),
        label: m.status ? (LIVE_LABEL[m.status] ?? m.status) : '进行中',
        time: new Date(m.startedAt).toTimeString().slice(0, 5),
      })),
      ...(source === 'mock' ? [{ id: 'mock' as SourceKey, title: '演示' }] : []),
      ...catalog.map((c) => ({
        id: `fixture:${c.id}` as SourceKey,
        title: c.title,
        phase: c.phase,
        label: c.label,
        time: c.startedAt,
      })),
    ]
    return all
      .filter((c) => !chats.overlay[c.id]?.deleted && !isVersionChild(c.id, chats))
      .map((c) => {
        // 会话显示当前版本的状态，标题与星标跟着根
        const cur = currentVersion(c.id, chats)
        const shown = cur === c.id ? c : (all.find((x) => x.id === cur) ?? c)
        const o = chats.overlay[c.id]
        return { ...shown, id: c.id, title: o?.title || c.title, starred: !!o?.starred }
      })
  }, [catalog, locals, metas, source, chats])

  const isLocal = display.startsWith('local:')
  const meta = liveId ? metas.find((m) => m.id === liveId) : undefined
  const rootItem = items.find((i) => i.id === source)
  const title = isLocal
    ? (rootItem?.title ?? locals.find((l) => l.id === source)?.title ?? '')
    : chats.overlay[source]?.title || live.title || (meta?.title ?? '')
  const messages = [...run.messages, ...(localMessages[display] ?? [])]
  const running = !!snap && !snap.exited && !snap.result
  const approvals = snap?.approvals ?? []
  const result = snap?.result && !turn.streaming ? snap.result : null
  const notice = isLocal
    ? startErr
    : (startErr ??
      (snap?.error
        ? snap.error
        : snap?.exited && !snap.result && live.phase === 'active'
          ? '进程已结束'
          : null))

  /** 起一个真实任务；返回 live: key */
  const launch = async (issue: string, repoPath: string): Promise<SourceKey> => {
    const mode = coreMode()
    const warrior = takeUnrestricted()
    const id = await startTask({ repo: repoPath, issue, mode, ...runChoices(getPrefs(), mode, warrior) })
    if (warrior) setWarriorTasks((s) => new Set(s).add(id))
    return `live:${id}` as SourceKey
  }

  const onSend = (text: string) => {
    if (isLocal && coreOk) {
      setStartErr(null)
      launch(text, repo)
        .then((key) => {
          setLocals((prev) => prev.filter((l) => l.id !== source))
          select(key)
        })
        .catch((e) => setStartErr(String(e instanceof Error ? e.message : e)))
      return
    }
    const stamp = clock()
    setLocalMessages((prev) => ({
      ...prev,
      [display]: [
        ...(prev[display] ?? []),
        { id: `u-${Date.now()}`, role: 'user', content: text, timestamp: stamp },
        { id: `a-${Date.now()}`, role: 'assistant', content: '收到。', meta: 'mock', timestamp: stamp },
      ],
    }))
  }

  /** 重试 / 编辑后重发：同一会话起新任务，作为新版本并切过去 */
  const newVersion = (kind: VersionKind, text?: string) => {
    const issue = (text ?? turn.user?.text ?? meta?.issue ?? '').trim()
    const repoPath = meta?.repo ?? (coreMode() === 'demo' ? '' : repo || lastRepo())
    setStartErr(null)
    launch(issue, repoPath)
      .then((key) => addVersion(source, key, kind))
      .catch((e) => setStartErr(String(e instanceof Error ? e.message : e)))
  }

  const versions = chats.versions[source]
  const turnActions = {
    enabled: !!coreOk && !running && !turn.streaming,
    onRetry: () => newVersion('retry'),
    onEdit: (text: string) => newVersion('edit', text),
    versions:
      versions && versions.list.length > 1
        ? { index: versions.sel, total: versions.list.length, at: versionAnchor(versions), onSelect: (i: number) => selectVersion(source, i) }
        : undefined,
    feedback: chats.feedback[display]?.rating,
    onFeedback: (rating: 'up' | 'down' | null, note?: string) => {
      setFeedback(display, rating ? { rating, note } : null)
      if (rating) toast('谢谢，已记下')
    },
  }

  const onNew = () => {
    const id = `local:${Date.now()}` as SourceKey
    setLocals((prev) => [{ id, title: '新会话' }, ...prev])
    select(id)
  }

  const doDelete = (id: string) => {
    const keys = deleteChat(id)
    for (const k of keys) if (k.startsWith('live:')) void forgetTask(k.slice('live:'.length))
    setLocals((prev) => prev.filter((l) => l.id !== id))
    if (id === source) {
      const next = items.find((i) => i.id !== id)
      if (next) select(next.id as SourceKey)
      else onNew()
    }
    toast('已删除')
  }

  const openSettings = (s?: string) => {
    if (s) setSection(s as SettingsSection)
    setView('settings')
  }

  const copyLast = () => {
    const text = [...turn.blocks.flatMap((b) => (b.type === 'text' ? [b.text] : [])), ...(turn.final ? [turn.final.text] : [])].join('\n\n')
    if (!text) return
    void navigator.clipboard?.writeText(text).then(() => toast('已复制最后一条回复'), () => toast('复制失败'))
  }

  const onKey = useEffectEvent((e: KeyboardEvent) => {
    const a = matchShortcut(e)
    if (!a) return
    if (a === 'stop') {
      if (e.defaultPrevented || dialogOpen() || !running || !liveId) return
      void cancelTask(liveId)
      return
    }
    if (dialogOpen() && a !== 'shortcuts' && a !== 'search') return
    e.preventDefault()
    const nav = (d: 1 | -1) => {
      const i = items.findIndex((x) => x.id === source)
      const next = items[(i + d + items.length) % items.length]
      if (next) select(next.id as SourceKey)
    }
    ;({
      newChat: onNew,
      search: () => (setShortcuts(false), setPalette((o) => !o)),
      toggleSidebar: () => setPrefs({ sidebarCollapsed: !getPrefs().sidebarCollapsed }),
      copyLast,
      focusInput: () => (setView('chat'), window.dispatchEvent(new Event('tw:focus-composer'))),
      upload: () => notYet('添加文件或图片'),
      settings: () => openSettings(),
      shortcuts: () => (setPalette(false), setShortcuts((o) => !o)),
      nextChat: () => nav(1),
      prevChat: () => nav(-1),
      modelMenu: () => (setView('chat'), window.dispatchEvent(new Event('tw:model-menu'))),
      effortMenu: () => (setView('chat'), window.dispatchEvent(new Event('tw:effort-menu'))),
    })[a]()
  })
  useEffect(() => {
    const h = (e: KeyboardEvent) => onKey(e)
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [])

  const renameTarget = renaming ? items.find((i) => i.id === renaming) : undefined
  const deleteTarget = deleting ? items.find((i) => i.id === deleting) : undefined

  return (
    <MotionConfig reducedMotion="user">
    <div className="app-grain flex h-full flex-col">
      <TitleBar
        title={view === 'settings' ? '设置' : title}
        sidebarOpen={!prefs.sidebarCollapsed}
        onToggleSidebar={() => setPrefs({ sidebarCollapsed: !prefs.sidebarCollapsed })}
      />
      <div className="flex min-h-0 flex-1">
        <Sidebar
          items={items}
          activeId={source}
          collapsed={prefs.sidebarCollapsed}
          userName={prefs.name}
          onSelect={(id) => select(id as SourceKey)}
          onNew={onNew}
          onSearch={() => setPalette(true)}
          onSettings={openSettings}
          onShortcuts={() => setShortcuts(true)}
          onRename={setRenaming}
          onDelete={setDeleting}
          onStar={toggleStar}
          settingsActive={view === 'settings'}
        />
        {view === 'settings' ? (
          <SettingsPage section={section} onSection={setSection} onBack={() => setView('chat')} onShortcuts={() => setShortcuts(true)} />
        ) : (
          <>
            <ChatPanel
              title={title || '三证'}
              run={isLocal ? null : live}
              turn={isLocal ? null : turn}
              draftKey={display}
              messages={messages}
              onSend={onSend}
              approvals={approvals}
              onApprove={liveId ? (rid, d, sc) => approve(liveId, rid, d, sc) : undefined}
              result={result}
              notice={notice}
              repo={
                isLocal && coreOk
                  ? { value: repo, onChange: setRepo, placeholder: coreMode() === 'demo' ? '演示仓库' : '仓库路径' }
                  : undefined
              }
              allowEmpty={isLocal && !!coreOk && coreMode() === 'demo'}
              running={running}
              onStop={liveId ? () => void cancelTask(liveId) : undefined}
              turnActions={isLocal ? undefined : turnActions}
              titleMenu={
                isLocal
                  ? undefined
                  : {
                      starred: !!chats.overlay[source]?.starred,
                      onStar: () => toggleStar(source),
                      onRename: () => setRenaming(source),
                      onDelete: () => setDeleting(source),
                    }
              }
              unrestricted={!!liveId && warriorTasks.has(liveId)}
            />
            <ActivityPanel
              key={display}
              title={isLocal ? '' : run.title.replace(/^(#\d+).*/, '$1') || 'SSH'}
              lines={feed.lines}
              activeRole={isLocal ? null : run.activeRole}
              onRestart={onRestart}
              onReveal={onReveal}
            />
          </>
        )}
      </div>
      <StatusBar />
      <ContextMenu />
      <Toaster />
      <SearchPalette
        open={palette}
        items={items.map((i) => ({ id: i.id, title: i.title, time: i.time, starred: i.starred }))}
        onClose={() => setPalette(false)}
        onSelect={(id) => select(id as SourceKey)}
        onNew={onNew}
      />
      <ShortcutsDialog open={shortcuts} onClose={() => setShortcuts(false)} />
      <RenameDialog
        open={!!renameTarget}
        initial={renameTarget?.title ?? ''}
        onClose={() => setRenaming(null)}
        onSave={(t) => {
          if (!renaming) return
          if (renaming.startsWith('local:')) setLocals((prev) => prev.map((l) => (l.id === renaming ? { ...l, title: t.trim() || l.title } : l)))
          renameChat(renaming, t)
        }}
      />
      <ConfirmDeleteDialog
        open={!!deleteTarget}
        title={deleteTarget?.title ?? ''}
        onClose={() => setDeleting(null)}
        onConfirm={() => deleting && doDelete(deleting)}
      />
    </div>
    </MotionConfig>
  )
}
