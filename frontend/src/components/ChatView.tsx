import { useRef, useEffect, useState } from 'react'
import type { DisplayMessage } from '../hooks/useChat'
import type { ModelInfo } from '../types'
import ChatInput from './ChatInput'
import logoSrc from '../assets/logo/logo.jpg'
import type { UploadedFile } from '../services/api'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface ChatViewProps {
  messages: DisplayMessage[]
  streaming: boolean
  onSend: (text: string, files?: UploadedFile[]) => void
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

/** Markdown 渲染组件 — 统一的样式配置 */
function MarkdownContent({ content }: { content: string }) {
  return (
    <Markdown
      remarkPlugins={[remarkGfm]}
      components={{
        // 标题
        h1: ({ children }) => <h1 className="text-xl font-bold mt-5 mb-2 text-gray-900">{children}</h1>,
        h2: ({ children }) => <h2 className="text-lg font-bold mt-4 mb-2 text-gray-900">{children}</h2>,
        h3: ({ children }) => <h3 className="text-base font-semibold mt-3 mb-1 text-gray-900">{children}</h3>,
        // 段落
        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
        // 列表
        ul: ({ children }) => <ul className="list-disc pl-5 mb-2 space-y-1">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal pl-5 mb-2 space-y-1">{children}</ol>,
        li: ({ children }) => <li className="text-sm leading-relaxed">{children}</li>,
        // 代码
        code: ({ className, children, ...props }) => {
          const isInline = !className
          return isInline ? (
            <code className="px-1 py-0.5 bg-gray-100 rounded text-sm font-mono text-pink-600" {...props}>
              {children}
            </code>
          ) : (
            <code className="block bg-gray-50 border border-gray-200 rounded-lg p-3 text-sm font-mono whitespace-pre-wrap my-2" {...props}>
              {children}
            </code>
          )
        },
        // 引用
        blockquote: ({ children }) => (
          <blockquote className="border-l-2 border-gray-300 pl-3 my-2 text-gray-500 italic">{children}</blockquote>
        ),
        // 分割线
        hr: () => <hr className="my-4 border-gray-200" />,
        // 表格（GFM）
        table: ({ children }) => (
          <div className="overflow-x-auto my-3">
            <table className="min-w-full text-sm border-collapse border border-gray-200">{children}</table>
          </div>
        ),
        thead: ({ children }) => <thead className="bg-gray-50">{children}</thead>,
        th: ({ children }) => <th className="border border-gray-200 px-3 py-2 text-left font-semibold text-gray-700">{children}</th>,
        td: ({ children }) => <td className="border border-gray-200 px-3 py-2 text-gray-700">{children}</td>,
        // 链接
        a: ({ href, children }) => (
          <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
            {children}
          </a>
        ),
        // 加粗
        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
      }}
    >
      {content}
    </Markdown>
  )
}

function MessageBubble({ msg }: { msg: DisplayMessage }) {
  const isUser = msg.role === 'user'

  const body = msg.content ? (
    isUser ? (
      <span className="whitespace-pre-wrap">{msg.content}</span>
    ) : (
      <MarkdownContent content={msg.content} />
    )
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
          <div className="rounded-2xl px-4 py-2.5 text-sm leading-relaxed bg-gray-100 text-gray-800">
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
      <div className={`text-sm leading-relaxed text-gray-800 px-1 ${msg.isStreaming ? 'animate-pulse-subtle' : ''}`}>
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
  const prevMsgLenRef = useRef(messages.length)
  const prevStreamingRef = useRef(streaming)

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

  // Auto-scroll: only on new message or streaming end (not on every token)
  useEffect(() => {
    const hasNewMessage = messages.length > prevMsgLenRef.current
    const streamingJustEnded = prevStreamingRef.current && !streaming
    prevMsgLenRef.current = messages.length
    prevStreamingRef.current = streaming

    if (!userAway && bottomRef.current && (hasNewMessage || streamingJustEnded)) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, streaming])

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
