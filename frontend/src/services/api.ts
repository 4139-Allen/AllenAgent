import type { ConversationListResponse, ModelsResponse, MemoryResponse } from '../types'

const BASE = '' // proxied by vite

export interface UploadedFile {
  name: string
  path: string
  type: string
  size: number
}

export interface FileUploadResponse {
  files: UploadedFile[]
}

let onUnauthorized: (() => void) | null = null

/** 注册 401 回调（由 App.tsx 在初始化时调用） */
export function setOnUnauthorized(cb: () => void) {
  onUnauthorized = cb
}

/** 获取当前 token */
export function getToken(): string | null {
  return localStorage.getItem('allen_token')
}

/** 401 的原因描述，供登录页展示 */
let lastAuthError: string | null = null

export function getLastAuthError(): string | null {
  return lastAuthError
}

function clearAuthState(reason: string) {
  lastAuthError = reason
  localStorage.removeItem('allen_token')
  localStorage.removeItem('allen_user')
  onUnauthorized?.()
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string>),
  }

  // 自动带 token
  const token = getToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
  })

  // 401 → token 失效，触发登出
  if (res.status === 401) {
    clearAuthState('登录已过期，请重新登录')
    throw new Error('登录已过期，请重新登录')
  }

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText}: ${text}`)
  }
  return res.json()
}

/* ── Auth ── */
export const authApi = {
  login: (phone: string, password: string) =>
    request<{ user: { id: string; phone: string; name: string; avatar_url: string }; token: { access_token: string; refresh_token: string; token_type: string; expires_in: number } }>(
      '/api/auth/login',
      { method: 'POST', body: JSON.stringify({ phone, password }) },
    ),

  register: (phone: string, password: string, name: string) =>
    request<{ user: { id: string; phone: string; name: string; avatar_url: string }; token: { access_token: string; refresh_token: string; token_type: string; expires_in: number } }>(
      '/api/auth/register',
      { method: 'POST', body: JSON.stringify({ phone, password, name }) },
    ),

  me: () => request<{ id: string; phone: string; name: string; avatar_url: string; role: string; created_at: string }>('/api/auth/me'),
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

/* ── Upload ── */
export const uploadApi = {
  files: async (files: File[]): Promise<FileUploadResponse> => {
    const formData = new FormData()
    for (const file of files) {
      formData.append('files', file)
    }
    const headers: Record<string, string> = {}
    const token = getToken()
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    const res = await fetch(`${BASE}/api/upload/files`, {
      method: 'POST',
      headers,
      body: formData,
    })
    if (!res.ok) {
      const text = await res.text().catch(() => '')
      throw new Error(`${res.status} ${res.statusText}: ${text}`)
    }
    return res.json()
  },
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
