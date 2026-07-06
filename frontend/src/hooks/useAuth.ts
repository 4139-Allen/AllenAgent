import { useState, useCallback } from 'react'

const TOKEN_KEY = 'allen_token'
const USER_KEY = 'allen_user'

interface UserInfo {
  id: string
  phone: string
  name: string
  avatar_url: string
}

interface LoginResponse {
  user: UserInfo
  token: {
    access_token: string
    refresh_token: string
    token_type: string
    expires_in: number
  }
}

export function useAuth() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY))
  const [user, setUser] = useState<UserInfo | null>(() => {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  })
  const [loading, setLoading] = useState(false)

  // 保存 token 到 localStorage
  const saveToken = useCallback((newToken: string, newUser: UserInfo) => {
    localStorage.setItem(TOKEN_KEY, newToken)
    localStorage.setItem(USER_KEY, JSON.stringify(newUser))
    setToken(newToken)
    setUser(newUser)
  }, [])

  // 清除登录态
  const clearAuth = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    setToken(null)
    setUser(null)
  }, [])

  // 刷新用户信息（头像上传/改名后调用）
  const refreshUser = useCallback(async () => {
    try {
      const t = localStorage.getItem(TOKEN_KEY)
      if (!t) return
      const res = await fetch('/api/auth/me', {
        headers: { 'Authorization': `Bearer ${t}` },
      })
      if (res.ok) {
        const data = await res.json()
        localStorage.setItem(USER_KEY, JSON.stringify(data))
        setUser(data)
      }
    } catch { /* ignore */ }
  }, [])

  // 登录
  const login = useCallback(async (phone: string, password: string) => {
    setLoading(true)
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone, password }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '登录失败' }))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      const data: LoginResponse = await res.json()
      saveToken(data.token.access_token, data.user)
    } finally {
      setLoading(false)
    }
  }, [saveToken])

  // 注册
  const register = useCallback(async (phone: string, password: string, name: string) => {
    setLoading(true)
    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone, password, name }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '注册失败' }))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      const data: LoginResponse = await res.json()
      saveToken(data.token.access_token, data.user)
    } finally {
      setLoading(false)
    }
  }, [saveToken])

  // 登出
  const logout = useCallback(async () => {
    if (token) {
      try {
        await fetch('/api/auth/logout', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
        })
      } catch {
        // ignore network errors on logout
      }
    }
    clearAuth()
  }, [token, clearAuth])

  return { token, user, loading, login, register, logout, clearAuth, refreshUser }
}
