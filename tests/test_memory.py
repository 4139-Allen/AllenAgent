"""对话记忆测试 — 滑动窗口、裁剪、工具消息管理"""

import pytest
from memory.short_term import ConversationMemory


def test_add_user_message(memory):
    """添加用户消息"""
    memory.add_message("user", "你好")
    history = memory.get_history()
    assert len(history) == 1
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "你好"


def test_add_assistant_message(memory):
    """添加助手消息"""
    memory.add_message("assistant", "你好！有什么可以帮你的？")
    history = memory.get_history()
    assert len(history) == 1
    assert history[0]["role"] == "assistant"


def test_add_tool_calls(memory):
    """添加工具调用消息"""
    tool_calls = [
        {"id": "call_1", "function": "search_web", "arguments": '{"query": "天气"}'}
    ]
    memory.add_tool_calls(tool_calls)
    msgs = memory.get_messages()
    assistant_msg = msgs[1]  # [0] = system prompt
    assert assistant_msg["role"] == "assistant"
    assert assistant_msg["tool_calls"][0]["id"] == "call_1"
    assert assistant_msg["tool_calls"][0]["function"]["name"] == "search_web"


def test_add_tool_result(memory):
    """添加工具结果"""
    memory.add_message("user", "天气怎么样")
    memory.add_tool_calls([{"id": "call_1", "function": "search_web", "arguments": '{"query": "天气"}'}])
    memory.add_tool_result("call_1", "search_web", "晴天 25度")
    msgs = memory.get_messages()
    tool_msg = msgs[3]  # system, user, assistant(tool_calls), tool
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == "call_1"
    assert tool_msg["content"] == "晴天 25度"


def test_sliding_window_trim(memory):
    """滑动窗口裁剪：超过 max_turns 时丢弃旧消息"""
    memory.max_turns = 2
    # 5 轮对话（10条消息），超过 max_messages = 2*4 = 8
    for i in range(5):
        memory.add_message("user", f"问题{i}")
        memory.add_message("assistant", f"回答{i}")
    history = memory.get_history()
    # 应裁剪到 <= max_messages
    assert len(history) <= memory.max_turns * 4
    assert "问题0" not in str(history), "最早的消息应被裁剪"


def test_trim_preserves_tool_sequences(memory):
    """裁剪不会切断 tool_calls → tool_results 的关联"""
    memory.max_turns = 1
    # 一轮包含工具的对话
    memory.add_message("user", "查天气")
    memory.add_tool_calls([{"id": "call_1", "function": "search_web", "arguments": '{"query": "天气"}'}])
    memory.add_tool_result("call_1", "search_web", "晴天")
    memory.add_message("assistant", "今天是晴天")

    # 再添加一轮，触发裁剪
    memory.add_message("user", "谢谢")
    memory.add_message("assistant", "不客气")

    history = memory.get_history()
    # 裁剪后不应出现孤立的 tool_calls 没有 tool_result
    for i, msg in enumerate(history):
        if msg["role"] == "assistant" and msg.get("tool_calls"):
            # 检查后面紧接着有对应的 tool_result
            assert i + 1 < len(history), f"tool_calls 没有对应的 tool_result"
            assert history[i + 1]["role"] == "tool", f"tool_calls 后面不是 tool_result"


def test_repair_orphaned_tool_calls(memory):
    """修复孤立的工具调用"""
    # 手动构造一个孤立 tool_calls（没有 tool_result）
    memory.add_message("user", "查天气")
    memory._messages.append({
        "role": "assistant",
        "content": None,
        "tool_calls": [{"id": "orphan", "type": "function", "function": {"name": "search_web", "arguments": "{}"}}],
    })
    # 再添加一个正常的
    memory.add_message("user", "你好")
    memory.add_message("assistant", "你好")

    result = memory.repair_orphaned_tool_calls()
    assert result, "应检测到并修复孤立消息"
    history = memory.get_history()
    assert not any(
        msg["role"] == "assistant" and msg.get("tool_calls") and msg["tool_calls"][0]["id"] == "orphan"
        for msg in history
    ), "孤立的 tool_calls 应被移除"


def test_extract_old_messages(memory):
    """提取早期消息用于压缩"""
    for i in range(5):
        memory.add_message("user", f"问题{i}")
        memory.add_message("assistant", f"回答{i}")
    old = memory.extract_old_messages(keep_recent=2)
    assert len(old) > 0, "应有早期消息被提取"
    # 检查提取的内容只包含 user 和 assistant
    for msg in old:
        assert msg["role"] in ("user", "assistant"), f"不应包含 {msg['role']} 消息"


def test_replace_old_with_summary(memory):
    """用摘要替换早期消息"""
    for i in range(5):
        memory.add_message("user", f"问题{i}")
        memory.add_message("assistant", f"回答{i}")

    memory.replace_old_with_summary("用户问了5个问题，都已回答", keep_recent=2)
    history = memory.get_history()
    assert history[0].get("_is_summary"), "第一条应为摘要"
    # summary + 保留的轮次
    assert len(history) <= 7
