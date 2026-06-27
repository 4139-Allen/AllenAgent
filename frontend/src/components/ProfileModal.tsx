import { useState, useEffect, useRef } from 'react'

interface ProfileData {
  name: string
  avatar: string | null
  memory: string
  memory_sections?: Record<string, string[]>
}

interface SectionEditorProps {
  name: string
  items: string[]
  newItem: string
  onRename: (old: string, newName: string) => void
  onDelete: () => void
  onRemoveItem: (idx: number) => void
  onAddItem: (val: string) => void
  onNewItemChange: (val: string) => void
}

function SectionEditor({ name, items, newItem, onRename, onDelete, onRemoveItem, onAddItem, onNewItemChange }: SectionEditorProps) {
  const [editing, setEditing] = useState(false)
  const [editValue, setEditValue] = useState(name)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (editing) {
      setEditValue(name)
      setTimeout(() => inputRef.current?.focus(), 0)
    }
  }, [editing])

  const save = () => {
    const val = editValue.trim()
    if (val && val !== name) onRename(name, val)
    setEditing(false)
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-1.5">
        {editing ? (
          <input
            ref={inputRef}
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onBlur={save}
            onKeyDown={(e) => { if (e.key === 'Enter') save() }}
            className="flex-1 text-sm font-medium text-gray-700 bg-transparent outline-none border-b border-gray-300 px-0 py-0.5"
          />
        ) : (
          <span
            onClick={() => setEditing(true)}
            className="flex-1 text-sm font-medium text-gray-700 cursor-pointer hover:text-gray-900"
          >
            {name}
          </span>
        )}
        <button
          onClick={onDelete}
          className="p-0.5 rounded text-gray-300 hover:text-red-500 transition-colors"
          title="删除段落"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>
      </div>

      <div className="space-y-1 mb-2">
        {items.map((item, idx) => (
          <div key={idx} className="flex items-center gap-2 group">
            <span className="flex-1 text-sm text-gray-700">{item}</span>
            <button
              onClick={() => onRemoveItem(idx)}
              className="p-0.5 rounded text-gray-300 hover:text-red-500 hover:bg-red-50 opacity-0 group-hover:opacity-100 transition-all"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2">
        <input
          value={newItem}
          onChange={(e) => onNewItemChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && newItem.trim()) {
              onAddItem(newItem.trim())
            }
          }}
          placeholder="添加条目..."
          className="flex-1 px-2 py-1 text-sm text-gray-600 placeholder-gray-300 bg-transparent outline-none border-b border-gray-100 focus:border-gray-300"
        />
        <button
          onClick={() => {
            if (newItem.trim()) onAddItem(newItem.trim())
          }}
          className="text-sm text-emerald-600 hover:text-emerald-700 font-medium"
        >
          添加
        </button>
      </div>
    </div>
  )
}

interface ProfileModalProps {
  open: boolean
  onClose: () => void
  onNameChange?: (name: string) => void
  onAvatarChange?: () => void
}

export default function ProfileModal({ open, onClose, onNameChange, onAvatarChange }: ProfileModalProps) {
  const [tab, setTab] = useState<'profile' | 'memory'>('profile')
  const [profile, setProfile] = useState<ProfileData | null>(null)
  const [name, setName] = useState('')
  const [memory, setMemory] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [sectionItems, setSectionItems] = useState<Record<string, string[]>>({})
  const [newItems, setNewItems] = useState<Record<string, string>>({})
  const fileRef = useRef<HTMLInputElement>(null)

  const DEFAULT_SECTION_NAMES = ['用户偏好', '项目约定', '重要事实', '待办']
  const [sectionNames, setSectionNames] = useState<string[]>(DEFAULT_SECTION_NAMES)

  useEffect(() => {
    if (!open) return
    setTab('profile')
    setSaved(false)
    fetch('/api/profile')
      .then((r) => r.json())
      .then((data) => {
        setProfile(data)
        setName(data.name)
        setMemory(data.memory)
        const s: Record<string, string[]> = {}
        const ni: Record<string, string> = {}
        const names = data.memory_sections ? Object.keys(data.memory_sections) : DEFAULT_SECTION_NAMES
        setSectionNames(names)
        for (const name of names) {
          s[name] = data.memory_sections?.[name] || []
          ni[name] = ''
        }
        setSectionItems(s)
        setNewItems(ni)
      })
      .catch(() => {})
  }, [open])

  const saveName = async () => {
    try {
      await fetch('/api/profile/name', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      })
      onNameChange?.(name)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) {
      console.error(e)
    }
  }

  const buildMemoryContent = () => {
    const lines = ['# Allen.md — Agent 持久记忆', '']
    for (const section of sectionNames) {
      const seen = new Set<string>()
      lines.push(`## ${section}`)
      for (const item of sectionItems[section] || []) {
        const trimmed = item.trim()
        if (trimmed && !seen.has(trimmed)) {
          seen.add(trimmed)
          lines.push(`- ${trimmed}`)
        }
      }
      lines.push('')
    }
    return lines.join('\n')
  }

  const saveMemory = async () => {
    setSaving(true)
    try {
      const content = buildMemoryContent()
      await fetch('/api/profile/memory', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) {
      console.error(e)
    } finally {
      setSaving(false)
    }
  }

  const handleAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (file.size > 1024 * 1024) {
      alert('头像不能超过 1MB')
      e.target.value = ''
      return
    }
    const form = new FormData()
    form.append('file', file)
    try {
      const res = await fetch('/api/profile/avatar', { method: 'POST', body: form })
      if (res.ok) {
        setProfile((p) => p ? { ...p, avatar: '/api/profile/avatar?t=' + Date.now() } : p)
        onAvatarChange?.()
      }
    } catch (e) {
      console.error(e)
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <h2 className="text-base font-medium text-gray-900">个人中心</h2>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-gray-100 text-gray-400">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-200 px-5">
          <button
            onClick={() => setTab('profile')}
            className={`py-2.5 text-sm font-medium border-b-2 transition-colors ${
              tab === 'profile' ? 'text-emerald-600 border-emerald-500' : 'text-gray-500 border-transparent hover:text-gray-700'
            }`}
          >
            个人信息
          </button>
          <button
            onClick={() => setTab('memory')}
            className={`py-2.5 text-sm font-medium border-b-2 transition-colors ml-6 ${
              tab === 'memory' ? 'text-emerald-600 border-emerald-500' : 'text-gray-500 border-transparent hover:text-gray-700'
            }`}
          >
            持久记忆
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {tab === 'profile' && (
            <div className="space-y-5">
              {/* Avatar */}
              <div className="flex items-center gap-4">
                <div
                  onClick={() => fileRef.current?.click()}
                  className="relative w-16 h-16 rounded-full overflow-hidden bg-gray-100 flex-shrink-0 cursor-pointer group"
                  title="点击更换头像"
                >
                  {profile?.avatar ? (
                    <img src={profile.avatar} alt="" className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-lg font-medium text-gray-400">
                      {(name || 'A')[0].toUpperCase()}
                    </div>
                  )}
                  <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                    <svg className="w-5 h-5 text-white opacity-0 group-hover:opacity-100 transition-opacity" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                  </div>
                </div>
                <div>
                  <p className="text-xs text-gray-400">点击头像更换，支持 JPG / PNG，不超过 1MB</p>
                  {profile?.avatar && (
                    <a href={profile.avatar} target="_blank" className="text-xs text-emerald-600 hover:text-emerald-700 mt-1 inline-block">
                      查看大图
                    </a>
                  )}
                  <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={handleAvatarUpload} />
                </div>
              </div>

              {/* Name */}
              <div>
                <label className="text-xs font-medium text-gray-500 mb-1 block">显示名称</label>
                <div className="flex gap-2">
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-800 outline-none focus:border-gray-400 transition-colors"
                  />
                  <button
                    onClick={saveName}
                    className="px-4 py-2 bg-emerald-500 text-white text-sm rounded-lg hover:bg-emerald-600 transition-colors"
                  >
                    保存
                  </button>
                </div>
              </div>
            </div>
          )}

          {tab === 'memory' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-gray-500">持久记忆</span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      const name = prompt('新段落名称：')
                      if (!name?.trim()) return
                      setSectionNames((prev) => [...prev, name.trim()])
                      setSectionItems((prev) => ({ ...prev, [name.trim()]: [] }))
                      setNewItems((prev) => ({ ...prev, [name.trim()]: '' }))
                    }}
                    className="text-xs text-emerald-600 hover:text-emerald-700"
                  >
                    + 新建段落
                  </button>
                  <button
                    onClick={async () => {
                      if (confirm('确定清空所有持久记忆？')) {
                        await fetch('/api/profile/memory', { method: 'DELETE' })
                        const empty: Record<string, string[]> = {}
                        const ni: Record<string, string> = {}
                        for (const n of sectionNames) { empty[n] = []; ni[n] = '' }
                        setSectionItems(empty)
                        setNewItems(ni)
                        setSaved(true)
                        setTimeout(() => setSaved(false), 2000)
                      }
                    }}
                    className="text-xs text-red-500 hover:text-red-600"
                  >
                    清空
                  </button>
                </div>
              </div>

              {sectionNames.map((section) => (
                <SectionEditor
                  key={section}
                  name={section}
                  items={sectionItems[section] || []}
                  newItem={newItems[section] || ''}
                  onRename={(oldName, newName) => {
                    setSectionNames((prev) => prev.map((s) => s === oldName ? newName : s))
                    setSectionItems((prev) => {
                      const items = prev[oldName]
                      const next = { ...prev }
                      delete next[oldName]
                      next[newName] = items || []
                      return next
                    })
                    setNewItems((prev) => {
                      const val = prev[oldName] || ''
                      const next = { ...prev }
                      delete next[oldName]
                      next[newName] = val
                      return next
                    })
                  }}
                  onDelete={() => {
                    setSectionNames((prev) => prev.filter((s) => s !== section))
                    setSectionItems((prev) => {
                      const next = { ...prev }
                      delete next[section]
                      return next
                    })
                    setNewItems((prev) => {
                      const next = { ...prev }
                      delete next[section]
                      return next
                    })
                  }}
                  onRemoveItem={(idx) => {
                    setSectionItems((prev) => ({
                      ...prev,
                      [section]: prev[section].filter((_, i) => i !== idx),
                    }))
                  }}
                  onAddItem={(val) => {
                    setSectionItems((prev) => ({
                      ...prev,
                      [section]: [...(prev[section] || []), val],
                    }))
                    setNewItems((prev) => ({ ...prev, [section]: '' }))
                  }}
                  onNewItemChange={(val) => setNewItems((prev) => ({ ...prev, [section]: val }))}
                />
              ))}

              <button
                onClick={saveMemory}
                disabled={saving}
                className="w-full py-2 bg-emerald-500 text-white text-sm rounded-lg hover:bg-emerald-600 disabled:opacity-50 transition-colors"
              >
                {saving ? '保存中...' : '保存记忆'}
              </button>
            </div>
          )}
        </div>

        {/* Save indicator */}
        {saved && (
          <div className="px-5 pb-3">
            <p className="text-xs text-emerald-600">已保存</p>
          </div>
        )}
      </div>
    </div>
  )
}
