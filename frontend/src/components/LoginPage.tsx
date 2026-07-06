import { useState } from 'react'
import type { FormEvent } from 'react'
import logoSrc from '../assets/logo/logo.jpg'

interface LoginPageProps {
  onLogin: (phone: string, password: string) => Promise<void>
  onRegister: (phone: string, password: string, name: string) => Promise<void>
  loading: boolean
  error?: string | null
}

type Tab = 'login' | 'register'

export default function LoginPage({ onLogin, onRegister, loading, error }: LoginPageProps) {
  const [tab, setTab] = useState<Tab>('login')
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)

  const displayError = error || localError

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setLocalError(null)

    // 表单校验
    if (!phone.trim()) {
      setLocalError('请输入手机号')
      return
    }
    if (!/^\d{6,15}$/.test(phone.trim())) {
      setLocalError('手机号格式不正确（6-15位数字）')
      return
    }
    if (!password || password.length < 6) {
      setLocalError('密码至少6位')
      return
    }
    if (tab === 'register' && !name.trim()) {
      setLocalError('请输入昵称')
      return
    }

    try {
      if (tab === 'login') {
        await onLogin(phone.trim(), password)
      } else {
        await onRegister(phone.trim(), password, name.trim() || `用户${phone.slice(-4)}`)
      }
    } catch (err) {
      setLocalError((err as Error).message)
    }
  }

  return (
    <div className="h-screen bg-white flex items-center justify-center">
      <div className="w-full max-w-sm mx-auto px-6">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <img src={logoSrc} alt="Allen Agent" className="w-16 h-16 rounded-2xl object-cover mb-4" />
          <h1 className="text-xl font-semibold text-gray-900">Allen Agent</h1>
          <p className="text-sm text-gray-500 mt-1">登录以继续使用</p>
        </div>

        {/* Tab: 登录 / 注册 */}
        <div className="flex mb-6 bg-gray-100 rounded-lg p-1">
          <button
            onClick={() => { setTab('login'); setLocalError(null) }}
            className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
              tab === 'login' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            登录
          </button>
          <button
            onClick={() => { setTab('register'); setLocalError(null) }}
            className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
              tab === 'register' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            注册
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* 手机号 */}
          <div>
            <label className="block text-sm text-gray-600 mb-1">手机号</label>
            <input
              type="text"
              inputMode="numeric"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="请输入手机号"
              className="w-full px-3 py-2.5 text-sm border border-gray-300 rounded-lg focus:border-gray-400 focus:outline-none transition-colors"
              autoComplete="tel"
            />
          </div>

          {/* 昵称（注册时显示） */}
          {tab === 'register' && (
            <div>
              <label className="block text-sm text-gray-600 mb-1">昵称</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="给自己起个名字"
                className="w-full px-3 py-2.5 text-sm border border-gray-300 rounded-lg focus:border-gray-400 focus:outline-none transition-colors"
                autoComplete="name"
              />
            </div>
          )}

          {/* 密码 */}
          <div>
            <label className="block text-sm text-gray-600 mb-1">密码</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={tab === 'register' ? '至少6位密码' : '请输入密码'}
              className="w-full px-3 py-2.5 text-sm border border-gray-300 rounded-lg focus:border-gray-400 focus:outline-none transition-colors"
              autoComplete={tab === 'register' ? 'new-password' : 'current-password'}
            />
          </div>

          {/* Error */}
          {displayError && (
            <div className="text-sm text-red-500 bg-red-50 rounded-lg px-3 py-2">
              {displayError}
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 text-sm font-medium text-white bg-gray-900 rounded-lg hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                处理中...
              </>
            ) : (
              tab === 'login' ? '登录' : '注册并登录'
            )}
          </button>
        </form>
      </div>
    </div>
  )
}
