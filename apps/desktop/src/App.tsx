import { useCallback, useMemo, useState } from 'react'
import { Sidebar, type SidebarItem } from './components/Sidebar'
import { ChatPanel } from './components/ChatPanel'
import { ActivityPanel } from './components/ActivityPanel'
import { StatusBar } from './components/StatusBar'
import { SettingsPage } from './components/SettingsPage'
import { TitleBar } from './components/TitleBar'
import { ContextMenu } from './components/ContextMenu'
import { useEventFeed } from './hooks/useEventFeed'
import { useFixtureCatalog } from './hooks/useFixtureCatalog'
import { FIXTURES, FixtureSource, type FixtureName } from './data/sources/fixture'
import { createMockSource } from './data/sources/mock'
import { foldRun } from './data/mapEvent'
import { parseSourceParam, speedParam, writeSourceParam, type SourceKey } from './lib/sourceParam'
import type { ChatMessage, StreamLine } from './types'
import type { Phase } from './data/mapEvent'
import type { TaskMeta } from './bridge/liveTask'
import {
  approve,
  cancelTask,
  coreMode,
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

function clock() {
  const d = new Date()
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export default function App() {
  const catalog = useFixtureCatalog()
  const [source, setSource] = useState<SourceKey>(() => parseSourceParam(window.location.search))
  const [locals, setLocals] = useState<{ id: SourceKey; title: string }[]>([])
  const [localMessages, setLocalMessages] = useState<Record<string, ChatMessage[]>>({})
  const [revealedSeq, setRevealedSeq] = useState(-1)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [view, setView] = useState<'chat' | 'settings'>(() =>
    new URLSearchParams(window.location.search).get('view') === 'settings' ? 'settings' : 'chat',
  )

  const coreOk = useCoreAvailable()
  const metas = useTaskMetas()
  const liveId = source.startsWith('live:') ? source.slice('live:'.length) : null
  const liveTask = useLiveTask(liveId)
  const snap = useLiveSnapshot(liveTask)
  const [repo, setRepo] = useState(() => (coreMode() === 'demo' ? '' : lastRepo()))
  const [startErr, setStartErr] = useState<string | null>(null)

  const feed = useEventFeed(liveId && !liveTask ? `${source}${PENDING}` : source, makeSource)

  // 状态 / 对话 / 费用都只折叠到“笔尖已写到”的那一行：暂停时一起停
  const run = useMemo(() => foldRun(feed.events, revealedSeq), [feed.events, revealedSeq])

  const select = useCallback((key: SourceKey) => {
    setSource(key)
    setRevealedSeq(-1)
    writeSourceParam(key)
    setView('chat')
  }, [])

  const onReveal = useCallback((line: StreamLine | null) => setRevealedSeq(line?.seq ?? -1), [])
  const onRestart = useCallback(() => {
    setRevealedSeq(-1)
    feed.restart()
  }, [feed])

  const items: SidebarItem[] = useMemo(
    () => [
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
    ],
    [catalog, locals, metas, source],
  )

  const isLocal = source.startsWith('local:')
  const meta = liveId ? metas.find((m) => m.id === liveId) : undefined
  const title = isLocal ? (locals.find((l) => l.id === source)?.title ?? '') : run.title || (meta?.title ?? '')
  const messages = [...run.messages, ...(localMessages[source] ?? [])]
  const running = !!snap && !snap.exited && !snap.result
  // 跟笔同步：审批卡等笔尖写到那一行再出；结论卡等笔写完最后一行
  const approvals = useMemo(() => snap?.approvals.filter((a) => a.seq <= revealedSeq) ?? [], [snap, revealedSeq])
  const result = snap?.result && liveTask && revealedSeq >= liveTask.afterSeq ? snap.result : null
  const notice = isLocal
    ? startErr
    : snap?.error
      ? snap.error
      : snap?.exited && !snap.result && liveTask && revealedSeq >= liveTask.afterSeq && run.phase === 'active'
        ? '进程已结束'
        : null

  const onSend = (text: string) => {
    if (isLocal && coreOk) {
      setStartErr(null)
      startTask({ repo, issue: text, mode: coreMode() })
        .then((id) => {
          setLocals((prev) => prev.filter((l) => l.id !== source))
          select(`live:${id}` as SourceKey)
        })
        .catch((e) => setStartErr(String(e instanceof Error ? e.message : e)))
      return
    }
    const stamp = clock()
    setLocalMessages((prev) => ({
      ...prev,
      [source]: [
        ...(prev[source] ?? []),
        { id: `u-${Date.now()}`, role: 'user', content: text, timestamp: stamp },
        { id: `a-${Date.now()}`, role: 'assistant', content: '收到。', meta: 'mock', timestamp: stamp },
      ],
    }))
  }

  const onNew = () => {
    const id = `local:${Date.now()}` as SourceKey
    setLocals((prev) => [{ id, title: '新会话' }, ...prev])
    select(id)
  }

  return (
    <div className="app-grain flex h-full flex-col">
      <TitleBar
        title={view === 'settings' ? '设置' : title}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen((o) => !o)}
      />
      <div className="flex min-h-0 flex-1">
        {sidebarOpen && (
          <Sidebar
            items={items}
            activeId={source}
            onSelect={(id) => select(id as SourceKey)}
            onNew={onNew}
            onSettings={() => setView('settings')}
            settingsActive={view === 'settings'}
          />
        )}
        {view === 'settings' ? (
          <SettingsPage onBack={() => setView('chat')} />
        ) : (
          <>
            <ChatPanel
              title={title || '三证'}
              run={isLocal ? null : run}
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
            />
            <ActivityPanel
              key={source}
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
    </div>
  )
}
