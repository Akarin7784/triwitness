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

function makeSource(key: SourceKey) {
  const speed = speedParam(window.location.search)
  if (key === 'mock') return createMockSource({ speed })
  if (key.startsWith('fixture:')) {
    const name = key.slice('fixture:'.length) as FixtureName
    return new FixtureSource(name, FIXTURES[name], { speed })
  }
  return null
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

  const feed = useEventFeed(source, makeSource)

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
      ...(source === 'mock' ? [{ id: 'mock' as SourceKey, title: '演示' }] : []),
      ...catalog.map((c) => ({
        id: `fixture:${c.id}` as SourceKey,
        title: c.title,
        phase: c.phase,
        label: c.label,
        time: c.startedAt,
      })),
    ],
    [catalog, locals, source],
  )

  const isLocal = source.startsWith('local:')
  const title = isLocal ? (locals.find((l) => l.id === source)?.title ?? '') : run.title
  const messages = [...run.messages, ...(localMessages[source] ?? [])]

  const onSend = (text: string) => {
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
            <ChatPanel title={title || '三证'} run={isLocal ? null : run} messages={messages} onSend={onSend} />
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
