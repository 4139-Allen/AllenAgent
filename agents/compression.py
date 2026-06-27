"""
上下文管理 — 检查 token 使用量，超阈值时裁剪旧消息
手动调用 force=True 时走 LLM 压缩摘要
"""

from utils.token_counter import estimate_messages_tokens, estimate_tokens

# 默认上下文窗口大小（可根据模型动态调整）
DEFAULT_CONTEXT_WINDOW = 32000

# 自动裁剪阈值：达到上下文 95% 时触发
TRIM_RATIO = 0.95

# 裁剪后降到 70%，避免频繁触发
TARGET_RATIO = 0.70

# 手动压缩时保留的最近对话轮数
KEEP_RECENT_TURNS = 10


class ConversationCompressor:
    """上下文管理器 — 自动裁剪 / 手动压缩"""

    def __init__(self, llm_provider):
        self.llm_provider = llm_provider

    def check_and_compress(self, memory, current_conversation_id: str = None,
                           force: bool = False):
        """检查 token 数，超阈值时裁剪；手动触发时 LLM 压缩

        Args:
            memory: ConversationMemory 实例
            current_conversation_id: 当前对话 ID（用于追加 summary 到 JSONL）
            force: 为 True 时 LLM 摘要压缩（/compress 命令）
        """
        if not memory:
            return

        messages = memory.get_messages()
        total_tokens = estimate_messages_tokens(messages)

        context_window = getattr(self.llm_provider, 'context_window', DEFAULT_CONTEXT_WINDOW)

        if force:
            # 手动压缩 → LLM 摘要
            old_messages = memory.extract_old_messages(keep_recent=KEEP_RECENT_TURNS)
            if not old_messages:
                return
            summary = self._compress_with_llm(old_messages)
            memory.replace_old_with_summary(summary, keep_recent=KEEP_RECENT_TURNS)
            if current_conversation_id:
                from memory.conversation_store import ConversationStore
                store = ConversationStore()
                store.append_summary(current_conversation_id, summary)
            return

        # 自动裁剪 → token 超阈值时丢弃最早消息
        threshold = int(context_window * TRIM_RATIO)
        if total_tokens < threshold:
            return

        target = int(context_window * TARGET_RATIO)
        self._trim_to_target(memory, target)

    def _trim_to_target(self, memory, target_tokens: int):
        """从最早的消息开始丢弃（保留摘要），直到 token ≤ 目标值"""
        history = memory.get_history()
        if not history:
            return

        # 分离摘要消息（永远保留）
        summaries = [m for m in history if m.get("_is_summary")]
        non_summaries = [m for m in history if not m.get("_is_summary")]

        if not non_summaries:
            return

        # 从非摘要消息中从前往后丢弃
        for i in range(len(non_summaries)):
            kept = summaries + non_summaries[i:]
            tokens_now = estimate_messages_tokens(
                [{"role": "system", "content": memory.get_system_prompt() or ""}] + kept
            )
            if tokens_now <= target_tokens:
                memory._messages = kept
                return

        # 丢光了还不够 → 只保留摘要
        memory._messages = summaries

    def _compress_with_llm(self, messages: list[dict]) -> str:
        """用 LLM 压缩早期对话为摘要"""
        conversation_text = ""
        for msg in messages:
            role = "用户" if msg["role"] == "user" else "助手"
            content = msg.get("content", "")
            if content:
                if len(content) > 500:
                    content = content[:497] + "..."
                conversation_text += f"{role}: {content}\n\n"

        if not conversation_text.strip():
            return "早期对话已压缩（无重要内容）"

        compress_prompt = f"""请将以下对话压缩为一段简洁的摘要（100-200字），保留关键信息：
1. 用户的主要意图和需求
2. 得到的关键结论或结果
3. 未完成的事项（如有）

对话内容：
{conversation_text}

请直接输出摘要，不要添加任何前缀或解释。"""

        try:
            messages_for_llm = [
                {"role": "system", "content": "你是一个对话摘要助手，专门将对话压缩为简洁的摘要。"},
                {"role": "user", "content": compress_prompt},
            ]

            summary = ""
            for chunk in self.llm_provider.chat_stream(
                messages=messages_for_llm,
                temperature=0.3,
            ):
                if chunk["type"] in ("token", "content"):
                    summary += chunk["content"]

            return summary.strip() if summary.strip() else "早期对话已压缩"

        except Exception:
            # LLM 压缩失败，简单截取作为降级
            fallback_parts = []
            for msg in messages[:5]:
                role = "用户" if msg["role"] == "user" else "助手"
                content = msg.get("content", "")
                if content:
                    if len(content) > 100:
                        content = content[:97] + "..."
                    fallback_parts.append(f"{role}: {content}")
            return " | ".join(fallback_parts) if fallback_parts else "早期对话已压缩"
