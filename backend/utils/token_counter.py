"""Token 计算工具
用 tiktoken 精确计数，fallback 到字符估算
"""

import tiktoken


_ENCODING_CACHE = {}


def _get_encoding(model: str = "cl100k_base") -> tiktoken.Encoding:
    """获取缓存中的 encoding"""
    if model not in _ENCODING_CACHE:
        try:
            _ENCODING_CACHE[model] = tiktoken.get_encoding(model)
        except Exception:
            _ENCODING_CACHE[model] = None
    return _ENCODING_CACHE[model]


def estimate_tokens(text: str, model: str = "cl100k_base") -> int:
    """估算文本的 token 数（用 tiktoken 精确计数）

    Args:
        text: 要计数的文本
        model: encoding 模型名，默认 cl100k_base（deepseek/gpt-4 等通用）

    Returns:
        token 数
    """
    if not text:
        return 0
    encoding = _get_encoding(model)
    if encoding:
        try:
            return len(encoding.encode(text))
        except Exception:
            pass
    # fallback: 中英文混合估算
    # 中文 ~1.5 字/token，英文 ~4 字符/token
    return max(1, len(text) // 3)


def estimate_message_tokens(message: dict, model: str = "cl100k_base") -> int:
    """估算单条消息的 token 数"""
    total = 0
    total += 4  # 消息格式开销（role + metadata）
    content = message.get("content")
    if content:
        total += estimate_tokens(str(content), model)
    tool_calls = message.get("tool_calls")
    if tool_calls:
        for tc in tool_calls:
            func = tc.get("function", {})
            total += estimate_tokens(func.get("name", ""), model)
            total += estimate_tokens(func.get("arguments", ""), model)
    return total


def estimate_messages_tokens(messages: list[dict], model: str = "cl100k_base") -> int:
    """估算消息列表的总 token 数"""
    system_prompt = next((m for m in messages if m["role"] == "system"), None)
    # system prompt 特殊格式: 开头 ~12 token, 结尾 ~3 token
    overhead = 12 + 3 if system_prompt else 0
    return sum(estimate_message_tokens(m, model) for m in messages) + overhead
