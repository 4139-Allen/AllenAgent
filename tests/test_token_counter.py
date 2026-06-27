"""Token 计数器测试"""

import pytest
from utils.token_counter import estimate_tokens, estimate_message_tokens, estimate_messages_tokens


class TestEstimateTokens:
    def test_empty(self):
        assert estimate_tokens("") == 0
        assert estimate_tokens(None) == 0

    def test_english(self):
        """英文文本"""
        # "hello world" = 2 tokens (cl100k_base)
        tokens = estimate_tokens("hello world")
        assert tokens > 0

    def test_chinese(self):
        """中文文本"""
        tokens = estimate_tokens("你好世界")
        assert tokens > 0

    def test_mixed(self):
        """中英文混合"""
        tokens = estimate_tokens("hello 你好 world 世界")
        assert tokens > 0
        # 混合比纯英文 token 多
        en_tokens = estimate_tokens("hello world")
        zh_tokens = estimate_tokens("你好世界")
        assert tokens >= en_tokens + zh_tokens - 2  # 近似

    def test_long_text(self):
        """长文本"""
        text = "test " * 1000
        tokens = estimate_tokens(text)
        assert tokens > 100, "1000个词应有明显token数"


class TestEstimateMessage:
    def test_user_message(self):
        msg = {"role": "user", "content": "你好"}
        tokens = estimate_message_tokens(msg)
        assert tokens > 0

    def test_assistant_with_tool_calls(self):
        msg = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {"name": "search_web", "arguments": '{"query": "天气"}'},
            }],
        }
        tokens = estimate_message_tokens(msg)
        assert tokens > 0

    def test_tool_message(self):
        msg = {"role": "tool", "tool_call_id": "call_1", "content": "执行结果"}
        tokens = estimate_message_tokens(msg)
        assert tokens > 0


class TestEstimateMessages:
    def test_multiple_messages(self):
        messages = [
            {"role": "system", "content": "你是一个助手"},
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！"},
        ]
        total = estimate_messages_tokens(messages)
        # 3条消息合计
        single = sum(estimate_message_tokens(m) for m in messages)
        assert total >= single
