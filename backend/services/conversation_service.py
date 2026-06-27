"""
对话服务层

对话的 CRUD 操作。
"""

from memory.short_term import ConversationMemory
from memory.conversation_store import ConversationStore


def list_conversations(store: ConversationStore, page: int = 1, page_size: int = 20):
    """分页获取对话列表"""
    all_ = store.list_all()
    total = len(all_)
    start = (page - 1) * page_size
    items = all_[start:start + page_size] if start < total else []
    return {
        "items": [
            {
                "id": c["id"],
                "title": c.get("title", ""),
                "turn_count": c.get("turn_count", 0),
            }
            for c in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def create_conversation(store: ConversationStore, max_turns: int):
    """新建空对话"""
    memory = ConversationMemory(max_turns=max_turns)
    conv_id = store.save(memory)
    return {"id": conv_id, "title": "", "turn_count": 0}


def get_conversation(store: ConversationStore, conv_id: str):
    """获取对话详情"""
    loaded = store.load(conv_id)
    return {
        "id": conv_id,
        "title": loaded.title,
        "turn_count": loaded.turn_count,
        "history": loaded.get_history(),
    }


def delete_conversation(store: ConversationStore, conv_id: str) -> bool:
    """删除对话"""
    return store.delete(conv_id)
