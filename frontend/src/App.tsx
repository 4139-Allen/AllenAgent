import { useState, useEffect, useCallback, useRef } from 'react'
import Sidebar from './components/Sidebar'
import ChatView from './components/ChatView'
import ProfileModal from './components/ProfileModal'
import { useConversations } from './hooks/useConversations'
import { useChat } from './hooks/useChat'
import { conversationsApi, modelsApi } from './services/api'
import type { ModelInfo } from './types'

export default function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [currentModel, setCurrentModel] = useState('')
  const [models, setModels] = useState<ModelInfo[]>([])
  const [profileOpen, setProfileOpen] = useState(false)
  const [reasoningEffort, setReasoningEffort] = useState('low')
  const [userName, setUserName] = useState('ALLen')
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null)
  const [initDone, setInitDone] = useState(false)
  const convs = useConversations()
  const chat = useChat()
  const loadingConvRef = useRef(false)

  // Init: fetch models and profile
  useEffect(() => {
    Promise.all([
      modelsApi.list(),
      fetch('/api/profile').then((r) => r.json()).catch(() => null),
    ])
      .then(([modelsRes, profile]) => {
        setModels(modelsRes.models)
        setCurrentModel(modelsRes.current)
        if (profile?.name) setUserName(profile.name)
        if (profile?.avatar) setAvatarUrl(profile.avatar)
      })
      .catch(() => {})
      .finally(() => setInitDone(true))
  }, [])

  // Load conversation history when switching
  useEffect(() => {
    if (!convs.currentId || loadingConvRef.current) return
    loadingConvRef.current = true
    conversationsApi
      .get(convs.currentId)
      .then((data) => {
        chat.loadHistory(data.history || [])
      })
      .catch(() => {
        chat.clearMessages()
      })
      .finally(() => {
        loadingConvRef.current = false
      })
  }, [convs.currentId])

  const handleSwitchModel = useCallback(async (model: string) => {
    try {
      const res = await modelsApi.switch(model)
      if (res.status === 'ok') {
        setCurrentModel(res.current_model)
      }
    } catch (e) {
      console.error('切换模型失败:', e)
    }
  }, [])

  const handleSend = useCallback(
    async (text: string) => {
      let convId = convs.currentId
      if (!convId) {
        // No conversation yet — create one before sending
        convId = await convs.create()
        if (!convId) return
      }

      const finalId = await chat.sendMessage(text, convId, reasoningEffort)
      if (finalId) {
        convs.updateAfterStream(finalId)
      }
    },
    [convs, chat],
  )

  const handleNewChat = useCallback(async () => {
    chat.clearMessages()
    convs.switchTo(null)
  }, [chat, convs])

  const handleSelectConversation = useCallback(
    (id: string) => {
      if (chat.streaming) return
      convs.switchTo(id)
    },
    [convs, chat.streaming],
  )

  const handleDeleteConversation = useCallback(
    async (id: string) => {
      await convs.remove(id)
      chat.clearMessages()
    },
    [convs, chat],
  )

  const handlePin = useCallback(
    async (id: string) => {
      try {
        const res = await conversationsApi.pin(id)
        if (res.status === 'ok') {
          convs.fetchList()
        }
      } catch (e) {
        console.error('置顶失败:', e)
      }
    },
    [convs],
  )

  const handleCompress = useCallback(
    async (id: string) => {
      try {
        const res = await conversationsApi.compress(id)
        if (res.status === 'ok') {
          // 压缩后刷新列表和当前对话
          convs.fetchList()
          if (convs.currentId === id) {
            const data = await conversationsApi.get(id)
            chat.loadHistory(data.history || [])
          }
        }
      } catch (e) {
        console.error('压缩失败:', e)
      }
    },
    [convs, chat],
  )

  if (!initDone) {
    return (
      <div className="h-screen bg-white flex items-center justify-center">
        <div className="flex items-center gap-2 text-gray-400">
          <div className="w-4 h-4 border-2 border-gray-300 border-t-emerald-500 rounded-full animate-spin" />
          <span className="text-sm">加载中...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen flex bg-white text-gray-900 overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        conversations={convs.list}
        currentId={convs.currentId}
        userName={userName}
        avatarUrl={avatarUrl}
        onNew={handleNewChat}
        onSelect={handleSelectConversation}
        onDelete={handleDeleteConversation}
        onPin={handlePin}
        onCompress={handleCompress}
        onSettings={() => setProfileOpen(true)}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((v) => !v)}
      />
      <ProfileModal open={profileOpen} onClose={() => setProfileOpen(false)} onNameChange={setUserName} onAvatarChange={() => setAvatarUrl('/api/profile/avatar?t=' + Date.now())} />

      {/* Sidebar reopen button (visible when collapsed) */}
      {sidebarCollapsed && (
        <button
          onClick={() => setSidebarCollapsed(false)}
          className="fixed top-2 left-2 z-50 p-2 rounded-lg bg-white border border-gray-300 text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors shadow-sm"
          title="打开侧边栏"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
      )}

      <ChatView
        messages={chat.messages}
        streaming={chat.streaming}
        onSend={handleSend}
        onStop={chat.stopStreaming}
        currentModel={currentModel}
        models={models}
        reasoningEffort={reasoningEffort}
        onReasoningEffortChange={setReasoningEffort}
        onNewChat={handleNewChat}
        onSwitchModel={handleSwitchModel}
      />
    </div>
  )
}
