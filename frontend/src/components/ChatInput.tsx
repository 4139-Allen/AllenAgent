import { useState, useRef, useEffect, KeyboardEvent } from 'react'
import type { ModelInfo } from '../types'

interface ChatInputProps {
  onSend: (text: string) => void
  onStop: () => void
  disabled: boolean
  streaming: boolean
  currentModel?: string
  models?: ModelInfo[]
  reasoningEffort?: string
  onReasoningEffortChange?: (val: string) => void
  onNewChat?: () => void
  onSwitchModel?: (model: string) => void
}

const EFFORT_OPTIONS = [
  { value: 'low', label: '低' },
  { value: 'medium', label: '中' },
  { value: 'high', label: '高' },
]

export default function ChatInput({
  onSend, onStop, disabled, streaming,
  currentModel, models, reasoningEffort, onReasoningEffortChange,
  onNewChat, onSwitchModel,
}: ChatInputProps) {
  const [text, setText] = useState('')
  const [showModelMenu, setShowModelMenu] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const [showPlusMenu, setShowPlusMenu] = useState(false)
  const plusMenuRef = useRef<HTMLDivElement>(null)
  const [showEffortMenu, setShowEffortMenu] = useState(false)
  const effortMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!streaming && textareaRef.current) {
      textareaRef.current.focus()
    }
  }, [streaming])

  // Close menus on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowModelMenu(false)
      }
      if (plusMenuRef.current && !plusMenuRef.current.contains(e.target as Node)) {
        setShowPlusMenu(false)
      }
      if (effortMenuRef.current && !effortMenuRef.current.contains(e.target as Node)) {
        setShowEffortMenu(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const autoResize = () => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
  }

  const handleSend = () => {
    const trimmed = text.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setText('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const modelLabel = models?.find((m) => m.model === currentModel)?.name || currentModel || ''

  return (
    <div className="bg-white">
      <div className="max-w-3xl mx-auto px-4 py-3">
        <div className="bg-white rounded-2xl border border-gray-300 focus-within:border-gray-400 transition-colors px-5 pt-3 pb-2 shadow-sm">
          {/* Row 1: textarea + stop button (only when streaming) */}
          <div className="flex items-end gap-2">
            <textarea
              ref={textareaRef}
              value={text}
              onChange={(e) => { setText(e.target.value); autoResize() }}
              onKeyDown={handleKeyDown}
              placeholder="输入消息..."
              rows={1}
              disabled={disabled}
              className="flex-1 bg-transparent text-gray-800 placeholder-gray-400 resize-none outline-none text-sm py-2 max-h-[300px] disabled:opacity-50"
            />
            {streaming && (
              <button
                onClick={onStop}
                className="flex-shrink-0 p-2 rounded-xl bg-red-100 text-red-500 hover:bg-red-200 transition-colors"
                title="停止生成"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <rect x="6" y="6" width="12" height="12" rx="1" />
                </svg>
              </button>
            )}
          </div>

          {/* Row 2: left = file + reasoning, right = model */}
          <div className="flex items-center justify-between mt-1">
            <div className="flex items-center gap-2">
              {/* File attach */}
              <div className="relative" ref={plusMenuRef}>
                <button
                  onClick={() => setShowPlusMenu((v) => !v)}
                  className="text-sm text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg px-1.5 py-1 transition-colors"
                  title="添加文件"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                </button>
                {showPlusMenu && (
                  <div className="absolute bottom-full left-0 mb-1 w-44 bg-white border border-gray-200 rounded-lg shadow-lg py-1 z-50">
                    <button className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 transition-colors">上传文件</button>
                    <button className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 transition-colors">粘贴图片</button>
                  </div>
                )}
              </div>

            </div>

            <div className="flex items-center gap-1">
              {/* Reasoning Effort (DeepSeek V4 / OpenAI o1/o3 专用) */}
              {onReasoningEffortChange && currentModel && (
                /deepseek-v4|^o[13]/.test(currentModel)
              ) && (
                <div className="relative" ref={effortMenuRef}>
                  <button
                    onClick={() => setShowEffortMenu((v) => !v)}
                    className="text-sm text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg px-2 py-1 transition-colors flex items-center gap-1"
                  >
                    {EFFORT_OPTIONS.find((o) => o.value === reasoningEffort)?.label || '低'}
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  {showEffortMenu && (
                    <div className="absolute bottom-full left-0 mb-1 w-24 bg-white border border-gray-200 rounded-lg shadow-lg py-1 z-50">
                      {EFFORT_OPTIONS.map((opt) => (
                        <button
                          key={opt.value}
                          onClick={() => {
                            onReasoningEffortChange(opt.value)
                            setShowEffortMenu(false)
                          }}
                          className={`w-full text-left px-3 py-1.5 text-sm transition-colors ${
                            reasoningEffort === opt.value
                              ? 'text-emerald-700 bg-emerald-50 font-medium'
                              : 'text-gray-600 hover:bg-gray-100 hover:text-gray-800'
                          }`}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Model selector */}
              <div className="relative" ref={menuRef}>
              <button
                onClick={() => setShowModelMenu((v) => !v)}
                className="text-sm text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg px-2 py-1 transition-colors flex items-center gap-1"
                title="切换模型"
              >
                <span className="max-w-[100px] truncate">{modelLabel || '选择模型'}</span>
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {showModelMenu && models && models.length > 0 && (
                <div className="absolute bottom-full right-0 mb-1 w-56 bg-white border border-gray-200 rounded-lg shadow-lg py-1 max-h-60 overflow-y-auto z-50">
                  {models.map((m) => (
                    <button
                      key={m.model}
                      onClick={() => {
                        onSwitchModel?.(m.model)
                        setShowModelMenu(false)
                      }}
                      className={`w-full text-left px-3 py-2 text-sm transition-colors ${
                        m.model === currentModel
                          ? 'text-emerald-700 bg-emerald-50 font-medium'
                          : 'text-gray-600 hover:bg-gray-100 hover:text-gray-800'
                      }`}
                    >
                      {m.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
