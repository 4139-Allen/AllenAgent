import { useState } from 'react'
import type { Conversation } from '../types'
import logoSrc from '../assets/logo/logo.jpg'

interface SidebarProps {
  conversations: Conversation[]
  currentId: string | null
  onNew: () => void
  onSelect: (id: string) => void
  onDelete: (id: string) => void
  onPin?: (id: string) => void
  onCompress?: (id: string) => void
  onSettings?: () => void
  userName?: string
  avatarUrl?: string | null
  collapsed: boolean
  onToggle: () => void
}

export default function Sidebar({
  conversations,
  currentId,
  onNew,
  onSelect,
  onDelete,
  onPin,
  onCompress,
  onSettings,
  userName,
  avatarUrl,
  collapsed,
  onToggle,
}: SidebarProps) {
  const [menuConvId, setMenuConvId] = useState<string | null>(null)

  return (
    <div
      className={`${
        collapsed ? 'w-0 overflow-hidden' : 'w-64'
      } flex-shrink-0 bg-gray-50 border-r border-gray-200 flex flex-col transition-all duration-200`}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-gray-200">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <img src={logoSrc} alt="Allen Agent" className="w-7 h-7 rounded-lg object-cover flex-shrink-0" />
          <span className="text-sm font-medium text-gray-900 truncate">Allen Agent</span>
        </div>
        <button
          onClick={onToggle}
          className="p-1.5 rounded-lg hover:bg-gray-200 text-gray-500 hover:text-gray-700 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
          </svg>
        </button>
      </div>

      {/* New Chat */}
      <div className="px-3 py-1.5">
        <button
          onClick={onNew}
          className="w-full flex items-center gap-2 px-2 py-2 rounded-lg text-gray-700 hover:bg-gray-100 hover:text-gray-900 transition-colors text-sm"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          新对话
        </button>
      </div>

      {/* Section Title */}
      <div className="px-3 pt-1 pb-1">
        <span className="text-[11px] font-medium text-gray-500 uppercase tracking-wider">历史对话</span>
      </div>

      {/* Conversation List */}
      <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-0.5">
        {conversations.length === 0 ? (
          <div className="text-center text-gray-500 text-xs py-8">暂无对话记录</div>
        ) : (
          conversations.map((conv) => (
            <div
              key={conv.id}
              className={`group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer text-sm transition-colors ${
                currentId === conv.id
                  ? 'bg-gray-200 text-gray-900'
                  : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900'
              }`}
              onClick={() => onSelect(conv.id)}
            >
              {conv.pinned && (
                <svg className="w-3 h-3 flex-shrink-0 text-gray-500" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M16 12V4h1V2H7v2h1v8l-2 2v2h5.2v6h1.6v-6H18v-2l-2-2z" />
                </svg>
              )}
              <span className="truncate flex-1">{conv.title || '新对话'}</span>

              {/* Menu button */}
              <div className="relative opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    setMenuConvId(menuConvId === conv.id ? null : conv.id)
                  }}
                  className="p-0.5 rounded hover:bg-gray-200 text-gray-600"
                >
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <circle cx="7" cy="12" r="1.5" />
                    <circle cx="12" cy="12" r="1.5" />
                    <circle cx="17" cy="12" r="1.5" />
                  </svg>
                </button>

                {menuConvId === conv.id && (
                  <>
                    <div className="fixed inset-0 z-10" onClick={() => setMenuConvId(null)} />
                    <div className="absolute right-0 top-0 z-20 w-36 bg-white border border-gray-200 rounded-lg shadow-lg py-1">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          onPin?.(conv.id)
                          setMenuConvId(null)
                        }}
                        className="w-full text-left px-3 py-1.5 text-sm text-gray-800 hover:bg-gray-100 flex items-center gap-2"
                      >
                        {conv.pinned ? '取消置顶' : '置顶'}
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          onCompress?.(conv.id)
                          setMenuConvId(null)
                        }}
                        className="w-full text-left px-3 py-1.5 text-sm text-gray-800 hover:bg-gray-100 flex items-center gap-2"
                      >
                        压缩
                      </button>
                      <hr className="my-1 border-gray-100" />
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          onDelete(conv.id)
                          setMenuConvId(null)
                        }}
                        className="w-full text-left px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 flex items-center gap-2"
                      >
                        删除
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* User section */}
      <div className="border-t border-gray-200 px-2 py-2">
        <div className="relative group">
          <button
            onClick={() => setMenuConvId(menuConvId === '__user__' ? null : '__user__')}
            className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <div className="w-7 h-7 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0 overflow-hidden">
              {avatarUrl ? (
                <img src={avatarUrl} alt="" className="w-full h-full object-cover" />
              ) : (
                <span className="text-xs font-medium text-emerald-600">{(userName || 'A')[0].toUpperCase()}</span>
              )}
            </div>
            <span className="text-sm text-gray-800 truncate">{userName || 'ALLen'}</span>
            <svg className="w-3 h-3 text-gray-400 ml-auto flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {menuConvId === '__user__' && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setMenuConvId(null)} />
              <div className="absolute bottom-full left-0 right-0 mb-1 bg-white border border-gray-200 rounded-lg shadow-lg py-1 z-20">
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    onSettings?.()
                    setMenuConvId(null)
                  }}
                  className="w-full text-left px-3 py-1.5 text-sm text-gray-800 hover:bg-gray-100 flex items-center gap-2"
                >
                  设置
                </button>
                <button className="w-full text-left px-3 py-1.5 text-sm text-gray-800 hover:bg-gray-100 flex items-center gap-2">
                  切换账号
                </button>
                <hr className="my-1 border-gray-100" />
                <button className="w-full text-left px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 flex items-center gap-2">
                  退出登录
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
