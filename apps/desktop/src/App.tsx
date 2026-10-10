import { useMemo, useState } from 'react'
import { Sidebar } from './components/Sidebar'
import { ChatPanel } from './components/ChatPanel'
import { ActivityPanel } from './components/ActivityPanel'
import { StatusBar } from './components/StatusBar'
import { SettingsPage } from './components/SettingsPage'
import { TitleBar } from './components/TitleBar'
import { ContextMenu } from './components/ContextMenu'
import { conversations as seedConversations, demoSession, messages as seedMessages } from './data/mock'
import type { ChatMessage, Conversation } from './types'

export default function App() {
  const [items, setItems] = useState<Conversation[]>(seedConversations)
  const [activeId, setActiveId] = useState(seedConversations[0]?.id ?? 'c1')
  const [messages, setMessages] = useState<ChatMessage[]>(seedMessages)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [view, setView] = useState<'chat' | 'settings'>(
    () => (new URLSearchParams(window.location.search).get('view') === 'settings' ? 'settings' : 'chat'),
  )

  const active = useMemo(
    () => items.find((c) => c.id === activeId) ?? items[0],
    [items, activeId],
  )

  const onSend = (text: string) => {
    const now = new Date()
    const stamp = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
    setMessages((prev) => [
      ...prev,
      {
        id: `u-${Date.now()}`,
        role: 'user',
        content: text,
        timestamp: stamp,
      },
      {
        id: `a-${Date.now()}`,
        role: 'assistant',
        content:
          '收到。',
        meta: 'mock',
        timestamp: stamp,
      },
    ])
  }

  const onNew = () => {
    const id = `c-${Date.now()}`
    const next: Conversation = {
      id,
      title: '未命名会话',
      preview: '新的三证任务',
      updatedAt: '现在',
      project: 'triwitness',
    }
    setItems((prev) => [next, ...prev])
    setActiveId(id)
    setMessages([
      {
        id: 'welcome',
        role: 'assistant',
        content: '纸页已铺好。',
        timestamp: '现在',
      },
    ])
  }

  return (
    <div className="app-grain flex h-full flex-col">
      <TitleBar
        title={view === 'settings' ? '设置' : active?.title}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen((o) => !o)}
      />
      <div className="flex min-h-0 flex-1">
        {sidebarOpen && <Sidebar
          items={items}
          activeId={active?.id ?? activeId}
          onSelect={(id) => {
            setActiveId(id)
            setView('chat')
          }}
          onNew={() => {
            onNew()
            setView('chat')
          }}
          onSettings={() => setView('settings')}
          settingsActive={view === 'settings'}
        />}
        {view === 'settings' ? (
          <SettingsPage onBack={() => setView('chat')} />
        ) : (
          <>
        <ChatPanel
          title={active?.title ?? '三证'}
          project={active?.project}
          messages={messages}
          onSend={onSend}
        />
            <ActivityPanel session={demoSession} />
          </>
        )}
      </div>
      <StatusBar />
      <ContextMenu />
    </div>
  )
}
