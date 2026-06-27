import type { StreamEvent } from '../types'

/**
 * Connect to the SSE chat stream.
 * Returns an AbortController so the caller can cancel mid-stream.
 */
export function chatStream(
  message: string,
  conversationId: string | null,
  onEvent: (event: StreamEvent) => void,
  onError: (error: string) => void,
  onDone: (conversationId: string) => void,
  reasoningEffort?: string,
): AbortController {
  const controller = new AbortController()

  fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, conversation_id: conversationId, reasoning_effort: reasoningEffort || undefined }),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const text = await response.text().catch(() => '')
        onError(`HTTP ${response.status}: ${text}`)
        return
      }

      const reader = response.body?.getReader()
      if (!reader) {
        onError('响应体为空')
        return
      }

      const decoder = new TextDecoder()
      let buffer = ''
      let finalConvId = conversationId || ''

      const readLoop = async () => {
        try {
          while (true) {
            const { done, value } = await reader.read()
            if (done) break

            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split('\n')
            buffer = lines.pop() || ''

            let currentEvent = ''

            for (const line of lines) {
              if (line.startsWith('event: ')) {
                currentEvent = line.slice(7).trim()
              } else if (line.startsWith('data: ')) {
                const data = line.slice(6)
                try {
                  const parsed = JSON.parse(data) as StreamEvent
                  if (parsed.type === 'meta' && parsed.content) {
                    try {
                      const meta = JSON.parse(parsed.content)
                      if (meta.conversation_id) finalConvId = meta.conversation_id
                    } catch {
                      // ignore
                    }
                  }
                  onEvent(parsed)
                } catch {
                  // JSON parse error - skip
                }
              }
            }
          }

          // Process remaining buffer
          if (buffer.startsWith('data: ')) {
            try {
              const parsed = JSON.parse(buffer.slice(6)) as StreamEvent
              onEvent(parsed)
            } catch {
              // ignore
            }
          }
        } catch (err) {
          if ((err as Error).name !== 'AbortError') {
            onError(String(err))
          }
        } finally {
          onDone(finalConvId)
        }
      }

      readLoop()
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        onError(String(err))
      }
    })

  return controller
}
