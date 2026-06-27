import { useState, useRef, useCallback } from 'react'
import type { StreamEvent } from '../types'
import { chatStream } from '../services/chat'

export interface DisplayMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  thinking?: string        // separate thinking content (collapsible)
  timestamp: number
  isStreaming?: boolean
}

let msgIdCounter = 0
function nextId() {
  return `msg_${Date.now()}_${++msgIdCounter}`
}

export function useChat() {
  const [messages, setMessages] = useState<DisplayMessage[]>([])
  const [streaming, setStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const thinkingRef = useRef(false)

  const appendAssistant = useCallback(() => {
    const id = nextId()
    setMessages((prev) => [
      ...prev,
      { id, role: 'assistant', content: '', thinking: '', timestamp: Date.now(), isStreaming: true },
    ])
    return id
  }, [])

  const updateLastAssistant = useCallback((text: string, append = false) => {
    setMessages((prev) => {
      const idx = prev.length - 1
      if (idx < 0 || prev[idx].role !== 'assistant') return prev
      const updated = [...prev]
      updated[idx] = {
        ...updated[idx],
        content: append ? updated[idx].content + text : text,
      }
      return updated
    })
  }, [])

  const appendThinking = useCallback((text: string) => {
    setMessages((prev) => {
      const idx = prev.length - 1
      if (idx < 0 || prev[idx].role !== 'assistant') return prev
      const updated = [...prev]
      updated[idx] = {
        ...updated[idx],
        thinking: (updated[idx].thinking || '') + text,
      }
      return updated
    })
  }, [])

  const finalizeAssistant = useCallback(() => {
    setMessages((prev) => {
      const idx = prev.length - 1
      if (idx < 0) return prev
      const updated = [...prev]
      updated[idx] = { ...updated[idx], isStreaming: false }
      return updated
    })
  }, [])

  const sendMessage = useCallback(
    (text: string, conversationId: string | null, reasoningEffort?: string): Promise<string | null> => {
      return new Promise((resolve) => {
        const userMsg: DisplayMessage = {
          id: nextId(),
          role: 'user',
          content: text,
          timestamp: Date.now(),
        }

        setMessages((prev) => [...prev, userMsg])
        setStreaming(true)
        thinkingRef.current = false

        appendAssistant()
        let finalConvId = conversationId || ''

        const controller = chatStream(
          text,
          conversationId,
          (event: StreamEvent) => {
            switch (event.type) {
              case 'thinking_start':
                thinkingRef.current = true
                break
              case 'thinking_token':
                if (event.content) {
                  appendThinking(event.content)
                }
                break
              case 'thinking_end':
                thinkingRef.current = false
                break
              case 'token':
                if (event.content) {
                  updateLastAssistant(event.content, true)
                }
                break
              case 'tool_call':
                const callArgs = event.args
                  ? JSON.stringify(event.args)
                  : ''
                appendThinking(
                  `\n[调用工具] ${event.name}${callArgs ? `\n${callArgs}` : ''}\n`,
                )
                break
              case 'tool_result':
                const resultText =
                  typeof event.result === 'string'
                    ? event.result
                    : JSON.stringify(event.result, null, 2)
                appendThinking(
                  `${resultText || ''}\n`,
                )
                break
              case 'reflection':
                appendThinking(
                  `\n[反思] (${event.ref_type || ''}): ${event.summary || ''}\n`,
                )
                break
              case 'error':
                updateLastAssistant(`\n[错误] ${event.content}\n\n`, true)
                break
              case 'done':
                break
            }
          },
          (error) => {
            updateLastAssistant(`\n\n[连接错误] ${error}`, true)
          },
          (convId: string) => {
            finalConvId = convId
            finalizeAssistant()
            setStreaming(false)
            resolve(finalConvId)
          },
          reasoningEffort,
        )

        abortRef.current = controller
      })
    },
    [appendAssistant, updateLastAssistant, appendThinking, finalizeAssistant],
  )

  const stopStreaming = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }
    finalizeAssistant()
    setStreaming(false)
  }, [finalizeAssistant])

  const clearMessages = useCallback(() => {
    setMessages([])
  }, [])

  const loadHistory = useCallback(
    (history: { role: string; content: string; _thinking?: string; tool_calls?: unknown }[]) => {
      const msgs: DisplayMessage[] = history
        .filter(
          (m) =>
            (m.role === 'user' || m.role === 'assistant') &&
            (m.role !== 'assistant' || m.content), // 跳过纯 tool_call 的 assistant 消息
        )
        .map((m) => ({
          id: nextId(),
          role: m.role as 'user' | 'assistant',
          content: m.content || '',
          thinking: (m as { _thinking?: string })._thinking || '',
          timestamp: Date.now(),
        }))
      setMessages(msgs)
    },
    [],
  )

  return {
    messages,
    streaming,
    sendMessage,
    stopStreaming,
    clearMessages,
    loadHistory,
  }
}
