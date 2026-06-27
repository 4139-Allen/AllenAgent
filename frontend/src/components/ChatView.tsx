import { useRef, useEffect, useState } from 'react'
import type { DisplayMessage } from '../hooks/useChat'
import type { ModelInfo } from '../types'
import ChatInput from './ChatInput'
import logoSrc from '../assets/logo/logo.jpg'

interface ChatViewProps {
  messages: DisplayMessage[]
  streaming: boolean
  onSend: (text: string) => void
  onStop: () => void
  currentModel?: string
  models?: ModelInfo[]
  reasoningEffort?: string
  onReasoningEffortChange?: (val: string) => void
  onNewChat?: () => void
  onSwitchModel?: (model: string) => void
}

function ThinkingBlock({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="mb-2">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 transition-colors"
      >
        <svg
          className={`w-3 h-3 transition-transform ${expanded ? 'rotate-90' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        思考过程
      </button>
      {expanded && (
        <div className="mt-1 text-sm text-gray-500 whitespace-pre-wrap border-l-2 border-gray-200 pl-3">
          {text}
        </div>
      )}
    </div>
  )
}

function MessageBubble({ msg }: { msg: DisplayMessage }) {
  const isUser = msg.role === 'user'

  const renderContent = (content: string) => {
    const parts = content.split(/(\*\*[^*]+\*\*)/g)
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>
      }
      return part
    })
  }

  const body = msg.content ? (
    renderContent(msg.content)
  ) : msg.isStreaming ? (
    <span className="inline-flex gap-1">
      <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
      <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
      <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
    </span>
  ) : (
    <span className="text-gray-400 italic">空响应</span>
  )

  if (isUser) {
    return (
      <div className="flex justify-end mb-6">
        <div className="max-w-[80%]">
          <div className="rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap bg-gray-100 text-gray-800">
            {body}
          </div>
        </div>
      </div>
    )
  }

  // Assistant: full width, no bubble, with collapsible thinking
  return (
    <div className="mb-6">
      {msg.thinking && <ThinkingBlock text={msg.thinking} />}
      <div className={`text-sm leading-relaxed whitespace-pre-wrap text-gray-800 px-1 ${msg.isStreaming ? 'animate-pulse-subtle' : ''}`}>
        {body}
      </div>
    </div>
  )
}

export default function ChatView({
  messages,
  streaming,
  onSend,
  onStop,
  currentModel,
  models,
  reasoningEffort,
  onReasoningEffortChange,
  onNewChat,
  onSwitchModel,
}: ChatViewProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const [userAway, setUserAway] = useState(false)
  const awayRef = useRef(false)

  // Track if user scrolled away from bottom (throttled via ref)
  const handleScroll = () => {
    const el = scrollRef.current
    if (!el) return
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    const isAway = distFromBottom > 120
    if (isAway !== awayRef.current) {
      awayRef.current = isAway
      setUserAway(isAway)
    }
  }

  // Auto-scroll only if user wasn't away
  useEffect(() => {
    if (!userAway && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages])

  return (
    <div className="flex-1 flex flex-col min-w-0 bg-white relative">
      {/* Jump to bottom button */}
      {userAway && streaming && (
        <button
          onClick={() => {
            setUserAway(false)
            bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
          }}
          className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10 px-4 py-1.5 bg-white border border-gray-300 rounded-full text-xs text-gray-500 shadow-sm hover:bg-gray-50 transition-colors"
        >
          回到底部
        </button>
      )}

      {/* Messages */}
      <div ref={scrollRef} onScroll={handleScroll} className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-3xl mx-auto">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-[60vh] text-center">
              <img src={logoSrc} alt="Allen Agent" className="w-14 h-14 rounded-2xl object-cover mb-4" />
              <h2 className="text-lg font-medium text-gray-800 mb-2">Allen Agent</h2>
              <p className="text-sm text-gray-500 max-w-md">
                RAG + ReAct Agent + 多引擎搜索 智能问答系统
              </p>
            </div>
          ) : (
            messages.map((msg) => <MessageBubble key={msg.id} msg={msg} />)
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input */}
      <ChatInput
        onSend={onSend}
        onStop={onStop}
        disabled={streaming}
        streaming={streaming}
        currentModel={currentModel}
        models={models}
        reasoningEffort={reasoningEffort}
        onReasoningEffortChange={onReasoningEffortChange}
        onNewChat={onNewChat}
        onSwitchModel={onSwitchModel}
      />
    </div>
  )
}
