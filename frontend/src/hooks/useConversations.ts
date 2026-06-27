import { useState, useEffect, useCallback } from 'react'
import type { Conversation } from '../types'
import { conversationsApi } from '../services/api'

export function useConversations() {
  const [list, setList] = useState<Conversation[]>([])
  const [currentId, setCurrentId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchList = useCallback(async () => {
    try {
      const res = await conversationsApi.list()
      setList(res.items)
    } catch (e) {
      console.error('获取对话列表失败:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchList()
  }, [fetchList])

  const create = useCallback(async () => {
    try {
      const conv = await conversationsApi.create()
      setList((prev) => [conv, ...prev])
      return conv.id
    } catch (e) {
      console.error('创建对话失败:', e)
      return null
    }
  }, [])

  const switchTo = useCallback(
    (id: string | null) => {
      setCurrentId(id)
    },
    [],
  )

  const remove = useCallback(
    async (id: string) => {
      try {
        await conversationsApi.delete(id)
        setList((prev) => prev.filter((c) => c.id !== id))
        if (currentId === id) {
          setCurrentId(null)
        }
      } catch (e) {
        console.error('删除对话失败:', e)
      }
    },
    [currentId],
  )

  const updateAfterStream = useCallback(
    (convId: string) => {
      setCurrentId(convId)
      fetchList()
    },
    [fetchList],
  )

  return { list, currentId, loading, create, switchTo, remove, updateAfterStream, fetchList }
}
