import type { Conversation, ConversationListResponse, ModelsResponse, MemoryResponse } from '../types'

const BASE = '' // proxied by vite

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText}: ${text}`)
  }
  return res.json()
}

/* ── Conversations ── */
export const conversationsApi = {
  list: (page = 1, pageSize = 50) =>
    request<ConversationListResponse>(`/api/conversations?page=${page}&page_size=${pageSize}`),

  create: () =>
    request<{ id: string; title: string; turn_count: number }>('/api/conversations', { method: 'POST' }),

  get: (id: string) =>
    request<{ id: string; turn_count: number; history: { role: string; content: string; tool_calls?: unknown }[] }>(
      `/api/conversations/${id}`
    ),

  delete: (id: string) =>
    request<{ status: string; id: string }>(`/api/conversations/${id}`, { method: 'DELETE' }),

  pin: (id: string) =>
    request<{ status: string; id: string; pinned: boolean }>(`/api/conversations/${id}/pin`, { method: 'POST' }),

  compress: (id: string) =>
    request<{ status: string; message: string; summary?: string }>(`/api/conversations/${id}/compress`, { method: 'POST' }),
}

/* ── Models ── */
export const modelsApi = {
  list: () => request<ModelsResponse>('/api/models'),
  switch: (model: string) =>
    request<{ status: string; message: string; current_model: string }>('/api/models/switch', {
      method: 'POST',
      body: JSON.stringify({ model }),
    }),
}

/* ── Memory ── */
export const memoryApi = {
  get: () => request<MemoryResponse>('/api/memory'),
  add: (fact: string) =>
    request<{ status: string; message: string }>('/api/memory', {
      method: 'POST',
      body: JSON.stringify({ fact }),
    }),
}

/* ── Health ── */
export const healthApi = {
  check: () => request<{ status: string; timestamp: number; model: string; version: string }>('/health'),
}
