import { useState, useRef, useEffect, useCallback } from 'react'
import type { KeyboardEvent } from 'react'
import type { ModelInfo } from '../types'
import { uploadApi, type UploadedFile } from '../services/api'

interface ChatInputProps {
  onSend: (text: string, files?: UploadedFile[]) => void
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

const ALLOWED_FILE_TYPES = [
  'image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp',
  'text/plain', 'application/pdf', 'text/csv', 'application/json',
  'text/markdown', 'text/x-python', 'text/javascript',
  'text/html', 'text/css',
]

export default function ChatInput({
  onSend, onStop, disabled, streaming,
  currentModel, models, reasoningEffort, onReasoningEffortChange,
  onNewChat: _onNewChat, onSwitchModel,
}: ChatInputProps) {
  const [text, setText] = useState('')
  const [showModelMenu, setShowModelMenu] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const [showPlusMenu, setShowPlusMenu] = useState(false)
  const plusMenuRef = useRef<HTMLDivElement>(null)
  const [showEffortMenu, setShowEffortMenu] = useState(false)
  const effortMenuRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // 待发送的文件列表（上传后的服务端文件信息）
  const [attachedFiles, setAttachedFiles] = useState<UploadedFile[]>([])
  const [uploading, setUploading] = useState(false)

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

  // ── 文件上传 ──
  const uploadFiles = useCallback(async (rawFiles: File[]): Promise<UploadedFile[]> => {
    setUploading(true)
    try {
      const res = await uploadApi.files(rawFiles)
      return res.files
    } catch (e) {
      console.error('上传文件失败:', e)
      return []
    } finally {
      setUploading(false)
    }
  }, [])

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const rawFiles = Array.from(e.target.files || [])
    if (!rawFiles.length) return

    // 先显示文件名（即使上传中）
    const tempFiles: UploadedFile[] = rawFiles.map((f) => ({
      name: f.name,
      path: '',
      type: f.type,
      size: f.size,
    }))
    setAttachedFiles((prev) => [...prev, ...tempFiles])

    // 上传
    const uploaded = await uploadFiles(rawFiles)
    setAttachedFiles((prev) => {
      // 把 tempFiles 替换为实际上传结果
      const remaining = [...prev]
      let uploadIdx = 0
      for (let i = remaining.length - 1; i >= 0; i--) {
        if (!remaining[i].path && uploadIdx < uploaded.length) {
          remaining[i] = uploaded[uploadIdx]
          uploadIdx++
        }
      }
      return remaining
    })

    // 重置 file input 以便重复选择同一个文件
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
    setShowPlusMenu(false)
  }

  const removeFile = (index: number) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index))
  }

  // ── 粘贴检测 ──
  const handlePaste = useCallback(async (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData?.items
    if (!items) return

    const imageFiles: File[] = []
    for (let i = 0; i < items.length; i++) {
      const item = items[i]
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile()
        if (file) {
          // 为粘贴的图片生成一个文件名
          const blob = new File([file], `clipboard_${Date.now()}.png`, { type: item.type })
          imageFiles.push(blob)
        }
      }
    }

    if (imageFiles.length > 0) {
      e.preventDefault()
      // 先显示预览
      const tempFiles: UploadedFile[] = imageFiles.map((f) => ({
        name: f.name,
        path: '',
        type: f.type,
        size: f.size,
      }))
      setAttachedFiles((prev) => [...prev, ...tempFiles])

      // 上传
      const uploaded = await uploadFiles(imageFiles)
      setAttachedFiles((prev) => {
        const remaining = [...prev]
        let uploadIdx = 0
        for (let i = remaining.length - 1; i >= 0; i--) {
          if (!remaining[i].path && uploadIdx < uploaded.length) {
            remaining[i] = uploaded[uploadIdx]
            uploadIdx++
          }
        }
        return remaining
      })
    }
  }, [uploadFiles])

  const handleSend = () => {
    const trimmed = text.trim()
    if (!trimmed && attachedFiles.length === 0) return
    if (disabled) return

    onSend(trimmed, attachedFiles.length > 0 ? attachedFiles : undefined)
    setText('')
    setAttachedFiles([])
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
          {/* Hidden file input */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={ALLOWED_FILE_TYPES.join(',')}
            className="hidden"
            onChange={handleFileSelect}
          />

          {/* File preview chips */}
          {attachedFiles.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-2">
              {attachedFiles.map((f, i) => (
                <div
                  key={i}
                  className="flex items-center gap-1.5 text-xs bg-gray-100 text-gray-700 rounded-lg px-2.5 py-1.5 max-w-[200px]"
                >
                  {/* File icon */}
                  {f.type.startsWith('image/') ? (
                    <svg className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  ) : (
                    <svg className="w-3.5 h-3.5 text-blue-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                    </svg>
                  )}
                  {/* File name */}
                  <span className="truncate">{f.name}</span>
                  {/* Uploading spinner or remove button */}
                  {!f.path ? (
                    <svg className="w-3 h-3 text-gray-400 animate-spin flex-shrink-0" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                  ) : (
                    <button
                      onClick={() => removeFile(i)}
                      className="p-0.5 rounded hover:bg-gray-200 text-gray-400 hover:text-gray-600 flex-shrink-0"
                    >
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Row 1: textarea + stop button (only when streaming) */}
          <div className="flex items-end gap-2">
            <textarea
              ref={textareaRef}
              value={text}
              onChange={(e) => { setText(e.target.value); autoResize() }}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              placeholder={attachedFiles.length > 0 ? '可选：输入描述信息...' : '输入消息...'}
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
            {/* Send button: only when not streaming */}
            {!streaming && (text.trim() || attachedFiles.length > 0) && (
              <button
                onClick={handleSend}
                disabled={uploading}
                className="flex-shrink-0 p-2 rounded-xl bg-emerald-100 text-emerald-600 hover:bg-emerald-200 disabled:opacity-50 transition-colors"
                title="发送"
              >
                {uploading ? (
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
                  </svg>
                )}
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
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                  </svg>
                </button>
                {showPlusMenu && (
                  <div className="absolute bottom-full left-0 mb-1 w-44 bg-white border border-gray-200 rounded-lg shadow-lg py-1 z-50">
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 transition-colors flex items-center gap-2"
                    >
                      <svg className="w-4 h-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 15V3" />
                      </svg>
                      上传文件
                    </button>
                    <div className="px-3 py-1.5 text-xs text-gray-400">
                      支持图片、TXT、PDF、代码文件
                    </div>
                    <div className="px-3 pb-1.5 text-xs text-gray-400">
                      也支持直接粘贴图片
                    </div>
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
