"""
对话服务层

对话的 CRUD 操作。
"""


def list_conversations(store, page: int = 1, page_size: int = 20, user_id: str | None = None):
    """分页获取对话列表"""
    all_ = store.list_all(user_id=user_id)
    total = len(all_)
    start = (page - 1) * page_size
    items = all_[start:start + page_size] if start < total else []
    return {
        "items": [
            {
                "id": c["id"],
                "title": c.get("title", ""),
                "turn_count": c.get("turn_count", 0),
                "pinned": c.get("pinned", False),
            }
            for c in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def create_conversation(store, max_turns: int, user_id: str | None = None):
    """新建空对话"""
    from memory.short_term import ConversationMemory
    memory = ConversationMemory(max_turns=max_turns)
    conv_id = store.save(memory, user_id=user_id)
    return {"id": conv_id, "title": "", "turn_count": 0}


def get_conversation(store, conv_id: str):
    """获取对话详情"""
    loaded = store.load(conv_id)
    return {
        "id": conv_id,
        "turn_count": loaded.turn_count,
        "history": loaded.get_history(),
    }


def delete_conversation(store, conv_id: str) -> bool:
    """删除对话"""
    return store.delete(conv_id)


def toggle_pin(store, conv_id: str) -> dict:
    """切换置顶状态"""
    pinned = store.toggle_pin(conv_id)
    return {"status": "ok", "id": conv_id, "pinned": pinned}


def compress_conversation(app_state, conv_id: str) -> dict:
    """用 LLM 压缩对话历史"""
    from memory.short_term import ConversationMemory

    store = app_state.store
    llm = app_state.model_manager.current_provider
    loaded = store.load(conv_id, context_window=0)

    from agents.compression import ConversationCompressor
    compressor = ConversationCompressor(llm)

    old_messages = loaded.extract_old_messages(keep_recent=5)
    if not old_messages:
        return {"status": "ok", "message": "对话已足够精简，无需压缩"}

    summary = compressor._compress_with_llm(old_messages)
    loaded.replace_old_with_summary(summary, keep_recent=5)
    store.save(loaded, conv_id)

    return {"status": "ok", "message": "对话已压缩", "summary": summary}
