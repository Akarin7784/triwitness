import { useEffect, useEffectEvent, useMemo, useState } from 'react'
import { Sidebar, type SidebarItem, type SidebarView } from './components/Sidebar'
import { ArtifactsPanel } from './components/ArtifactsPanel'
import { ProjectsPage } from './components/ProjectsPage'
import { ArtifactsPage, type ArtifactEntry } from './components/ArtifactsPage'
import { AnimatePresence } from 'framer-motion'
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
  rootOf,
  selectVersion,
  setFeedback,
  toggleStar,
  useChats,
  versionAnchor,
  type VersionKind,
} from './lib/chats'
import { matchShortcut } from './lib/shortcuts'
import { dialogOpen } from './lib/dialogState'
import { toast } from './lib/toast'
import { moveChat, projectOf, setChatProject, useProjects } from './lib/projects'
import { buildGuidance } from './lib/guidance'
import { collectArtifacts, type VersionSource } from './lib/artifacts'
import { chatToMarkdown, exportFileName } from './lib/exportChat'
import { copyText, saveText } from './lib/download'
import { printMarkdown } from './lib/printPdf'
import type { Attachment } from './lib/attachments'
import { getTransport } from './bridge/transport'
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
  const [view, setView] = useState<SidebarView>(() => {
    const v = params.get('view')
    return v === 'settings' || v === 'projects' || v === 'artifacts' ? v : 'chat'
  })
  const [openProject, setOpenProject] = useState<string | null>(null)
  const projects = useProjects()
  /** 作品栏：打开的作品 id 与版本；diffs 按 run_dir 缓存 patch.diff */
  const [artifact, setArtifact] = useState<{ id: string; version: number | null } | null>(null)
  const [diffs, setDiffs] = useState<Record<string, string | null>>({})
  const [section, setSection] = useState<SettingsSection>(() => (params.get('section') as SettingsSection) || 'general')
  const [palette, setPalette] = useState(false)
  const [shortcuts, setShortcuts] = useState(false)
  const [renaming, setRenaming] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)

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
    if (key !== source) setArtifact(null)
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
        return { ...shown, id: c.id, title: o?.title || c.title, starred: !!o?.starred, projectId: projects.chats[c.id] ?? null }
      })
  }, [catalog, locals, metas, source, chats, projects])

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

  /** 起一个真实任务；返回 live: key。个人资料 + 风格 + 项目说明进“用户设置”，项目知识文件随附件一起交给核心 */
  const launch = async (issue: string, repoPath: string, files: { name: string; path: string }[], chat: string): Promise<SourceKey> => {
    const mode = coreMode()
    const warrior = takeUnrestricted()
    const p = getPrefs()
    const project = projectOf(chat)
    const guidance = buildGuidance(p, project)
    const paths = [...files.map((f) => f.path), ...(project?.knowledge.map((k) => k.path) ?? [])]
    const id = await startTask({
      repo: repoPath,
      issue,
      mode,
      ...runChoices(p, mode, warrior),
      attachments: paths.length ? paths.slice(0, 20) : undefined,
      guidance: guidance || undefined,
      attachmentNames: files.map((f) => f.name),
      userAttachments: files.map((f) => f.path),
    })
    return `live:${id}` as SourceKey
  }

  const onSend = (text: string, atts: Attachment[] = []) => {
    if (isLocal && coreOk) {
      setStartErr(null)
      const files = atts.flatMap((a) => (a.path ? [{ name: a.name, path: a.path }] : []))
      launch(text, repo, files, source)
        .then((key) => {
          moveChat(source, key)
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
    const files = (meta?.attachmentPaths ?? []).map((path, i) => ({ path, name: meta?.attachments?.[i] ?? path }))
    setStartErr(null)
    launch(issue, repoPath, files, source)
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

  const onNew = (projectId?: string) => {
    const id = `local:${Date.now()}` as SourceKey
    setLocals((prev) => [{ id, title: '新会话' }, ...prev])
    if (projectId) setChatProject(id, projectId)
    select(id)
    window.setTimeout(() => window.dispatchEvent(new Event('tw:focus-composer')), 60)
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
      newChat: () => onNew(),
      search: () => (setShortcuts(false), setPalette((o) => !o)),
      toggleSidebar: () => setPrefs({ sidebarCollapsed: !getPrefs().sidebarCollapsed }),
      copyLast,
      focusInput: () => (setView('chat'), window.dispatchEvent(new Event('tw:focus-composer'))),
      upload: () => (setView('chat'), window.setTimeout(() => window.dispatchEvent(new Event('tw:attach-pick')), 30)),
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

  // ---- 作品：当前会话各版本的代码块 / patch.diff / pr.md ----
  const versionKeys = versions?.list ?? [source]
  const versionSources: VersionSource[] = versionKeys.map((k) => {
    const id = k.startsWith('live:') ? k.slice(5) : null
    const m = id ? metas.find((x) => x.id === id) : undefined
    const t = k === display ? turn : id && liveTaskFor(id) ? foldTurn(liveTaskFor(id)!.allEvents) : null
    const res = k === display ? (snap?.result ?? m?.result ?? null) : (m?.result ?? null)
    return { turn: t, prMd: res?.pr_md ?? null, diff: res?.run_dir ? (diffs[res.run_dir] ?? null) : null }
  })
  const artifacts = isLocal ? [] : collectArtifacts(versionSources)
  const runDirs = versionKeys
    .map((k) => (k.startsWith('live:') ? metas.find((x) => x.id === k.slice(5))?.result?.run_dir : undefined) ?? (k === display ? snap?.result?.run_dir : undefined))
    .filter((d): d is string => !!d)
  const missing = runDirs.filter((d) => !(d in diffs)).join('|')
  useEffect(() => {
    if (!missing) return
    let live = true
    void getTransport().then(async (t) => {
      if (!t) return
      for (const d of missing.split('|')) {
        const text = await t.readArtifact(d, 'patch.diff').catch(() => null)
        if (live) setDiffs((cur) => ({ ...cur, [d]: text && text.trim() ? text : null }))
      }
    })
    return () => {
      live = false
    }
  }, [missing])
  const openArt = artifact ? artifacts.find((a) => a.id === artifact.id) : undefined
  const verIndex = openArt ? (artifact?.version ?? openArt.versions.length - 1) : 0
  const openArtifact = (id: string) => setArtifact((cur) => (cur?.id === id ? null : { id, version: null }))
  const onOpenCode = useEffectEvent((code: string) => {
    const a = artifacts.find((x) => x.versions.some((v) => v.content === code))
    if (a) setArtifact({ id: a.id, version: a.versions.findIndex((v) => v.content === code) })
  })
  useEffect(() => {
    const h = (e: Event) => onOpenCode((e as CustomEvent<string>).detail)
    window.addEventListener('tw:open-artifact', h)
    return () => window.removeEventListener('tw:open-artifact', h)
  }, [])
  const onEsc = useEffectEvent((e: KeyboardEvent) => {
    if (e.key === 'Escape' && !e.defaultPrevented && artifact && !dialogOpen() && !running) setArtifact(null)
  })
  useEffect(() => {
    const h = (e: KeyboardEvent) => onEsc(e)
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [])

  // ---- 分享 / 导出（只在本机） ----
  const exportMd = () =>
    chatToMarkdown({
      title,
      turn: isLocal ? null : turn,
      messages: [...(isLocal || turn.user ? [] : run.messages), ...(localMessages[display] ?? [])],
      result,
      attachments: meta?.attachments,
    })
  const share = {
    copyMarkdown: () => void copyText(exportMd(), '已复制为 Markdown'),
    exportMarkdown: () => void saveText(exportFileName(title, 'md'), exportMd(), 'text/markdown'),
    exportPdf: () => printMarkdown(exportMd(), title || '三证会话'),
  }

  // ---- 作品页：所有任务的 pr.md / patch.diff ----
  const artifactEntries: ArtifactEntry[] = metas
    .filter((m) => m.result && !chats.overlay[`live:${m.id}`]?.deleted)
    .flatMap((m) => {
      const chat = rootOf(`live:${m.id}`, chats)
      const t = new Date(m.startedAt).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
      const chatTitle = chats.overlay[chat]?.title || m.title
      const out: ArtifactEntry[] = []
      if (m.result?.branch) out.push({ chat, chatTitle, artifact: 'patch.diff', title: 'patch.diff', kind: 'diff', time: t })
      if (m.result?.pr_md) out.push({ chat, chatTitle, artifact: 'pr.md', title: 'pr.md', kind: 'markdown', time: t })
      return out
    })
    .filter((e, i, all) => all.findIndex((x) => x.chat === e.chat && x.artifact === e.artifact) === i)

  const project = projectOf(source, projects)
  const permissionHigh = snap?.permission?.risk === 'high'

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
          onNew={() => onNew()}
          onSearch={() => setPalette(true)}
          onSettings={openSettings}
          onShortcuts={() => setShortcuts(true)}
          onRename={setRenaming}
          onDelete={setDeleting}
          onStar={toggleStar}
          settingsActive={view === 'settings'}
          view={view}
          onProjects={() => (setOpenProject(null), setView('projects'))}
          onArtifacts={() => setView('artifacts')}
          onOpenProject={(id) => (setOpenProject(id), setView('projects'))}
          projects={projects.projects.map((x) => ({ id: x.id, name: x.name }))}
          onProject={(chat, pid) => {
            setChatProject(chat, pid)
            toast(pid ? `已加入「${projects.projects.find((x) => x.id === pid)?.name ?? ''}」` : '已移出项目')
          }}
        />
        {view === 'settings' ? (
          <SettingsPage section={section} onSection={setSection} onBack={() => setView('chat')} onShortcuts={() => setShortcuts(true)} />
        ) : view === 'projects' ? (
          <ProjectsPage
            selected={openProject}
            onSelect={setOpenProject}
            chatsOf={(pid) => items.filter((i) => i.projectId === pid).map((i) => ({ id: i.id, title: i.title, time: i.time }))}
            onOpenChat={(id) => select(id as SourceKey)}
            onNewChat={(pid) => onNew(pid)}
          />
        ) : view === 'artifacts' ? (
          <ArtifactsPage
            entries={artifactEntries}
            onOpen={(e) => {
              select(e.chat as SourceKey)
              setArtifact({ id: e.artifact, version: null })
            }}
          />
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
                      projects: projects.projects.map((x) => ({ id: x.id, name: x.name })),
                      projectId: project?.id ?? null,
                      onProject: (pid) => {
                        setChatProject(source, pid)
                        toast(pid ? `已加入「${projects.projects.find((x) => x.id === pid)?.name ?? ''}」` : '已移出项目')
                      },
                    }
              }
              unrestricted={!!liveId && permissionHigh}
              share={isLocal ? undefined : share}
              artifacts={artifacts}
              activeArtifact={openArt?.id ?? null}
              onOpenArtifact={openArtifact}
              project={project?.name}
              sentAttachments={meta?.attachments}
            />
            <AnimatePresence mode="popLayout" initial={false}>
              {openArt ? (
                <ArtifactsPanel
                  key="artifact"
                  artifact={openArt}
                  width={prefs.artifactWidth}
                  version={verIndex}
                  onVersion={(i) => setArtifact({ id: openArt.id, version: i })}
                  onClose={() => setArtifact(null)}
                />
              ) : (
                <ActivityPanel
                  key={`activity:${display}`}
                  title={isLocal ? '' : run.title.replace(/^(#\d+).*/, '$1') || 'SSH'}
                  lines={feed.lines}
                  activeRole={isLocal ? null : run.activeRole}
                  onRestart={onRestart}
                  onReveal={onReveal}
                />
              )}
            </AnimatePresence>
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
        onNew={() => onNew()}
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
