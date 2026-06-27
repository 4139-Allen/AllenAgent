/* ===== Messages ===== */
export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  tool_calls?: ToolCall[]
  tool_call_id?: string
  timestamp: number
}

export interface ToolCall {
  id: string
  function: string
  arguments: string
}

/* ===== Conversations ===== */
export interface Conversation {
  id: string
  title: string
  turn_count: number
  created_at?: string
  file_size?: number
  pinned?: boolean
}

export interface ConversationListResponse {
  items: Conversation[]
  total: number
  page: number
  page_size: number
}

/* ===== Stream Events (matches backend StreamEvent) ===== */
export interface StreamEvent {
  type: string
  content?: string
  name?: string
  args?: Record<string, unknown>
  result?: unknown
  duration?: number
  step?: number
  total?: number
  count?: number
  tool_call_id?: string
  ref_type?: string
  summary?: string
  confirm_question?: string
  confirm_callback?: unknown
  tool_status?: string
  file_action?: string
  file_path?: string
}

/* ===== Models ===== */
export interface ModelInfo {
  name: string
  model: string
  protocol: string
  is_current: boolean
}

export interface ModelsResponse {
  models: ModelInfo[]
  current: string
}

/* ===== Memory ===== */
export interface MemoryResponse {
  content: string
}
