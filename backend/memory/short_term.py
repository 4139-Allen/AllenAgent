"""
对话记忆管理（纯内存）
- 滑动窗口保留最近 N 轮对话
- 支持 system prompt / user / assistant / tool 四种角色
- 为 Function Calling 的 tool messages 提供原生支持
"""

from typing import Optional


class ConversationMemory:
    """
    对话记忆

    消息结构：
        [system_prompt] + [历史消息（滑动窗口）]

    滑动窗口策略：
        保留最近 max_turns 轮对话。
        "一轮" = 一组 user + assistant/tool 消息。
        超出窗口的旧消息被丢弃（system prompt 始终保留）。
    """

    def __init__(self, max_turns: int = 10):
        self.max_turns = max_turns
        self._system_prompt: Optional[str] = None
        self._messages: list[dict] = []  # 不含 system

    def set_system_prompt(self, prompt: str):
        """设置系统提示词"""
        self._system_prompt = prompt

    def add_message(self, role: str, content: str, **kwargs):
        """
        添加一条消息

        Args:
            role: "user" 或 "assistant"
            content: 消息内容
            **kwargs: 其他字段（如 tool_calls）
        """
        msg = {"role": role, "content": content}
        msg.update(kwargs)
        self._messages.append(msg)
        self._trim()

    def add_tool_calls(self, tool_calls: list[dict]):
        """
        添加 assistant 的 tool_calls 消息

        Args:
            tool_calls: LLM 返回的 tool_calls 列表
                [{"id": "xxx", "function": "name", "arguments": "{...}"}]
        """
        msg = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["function"],
                        "arguments": tc["arguments"],
                    },
                }
                for tc in tool_calls
            ],
        }
        self._messages.append(msg)
        self._trim()

    def merge_last_tool_results(self, summary: str):
        """
        将最近一批 tool_calls + tool_results 合并为一条摘要。
        减少 context 膨胀，节省 token。
        """
        if not self._messages:
            return
        # 找到最后一个 assistant(tool_calls) 消息的位置
        idx = len(self._messages) - 1
        while idx >= 0:
            msg = self._messages[idx]
            if msg["role"] == "assistant" and msg.get("tool_calls"):
                break
            idx -= 1
        if idx < 0:
            return
        # 删除从 idx 开始到末尾的所有消息（assistant(tool_calls) + tool_results）
        del self._messages[idx:]
        # 替换为一条摘要
        self._messages.append({"role": "assistant", "content": summary})

    def undo_last_tool_calls(self):
        """
        撤销最近一次 add_tool_calls 及其后的所有 tool_result。
        用于用户拒绝执行工具时清理 memory，避免孤立的 tool_calls 导致 API 400 错误。
        """
        if not self._messages:
            return
        # 从末尾往前找最后一个 assistant(tool_calls) 消息
        idx = len(self._messages) - 1
        while idx >= 0:
            msg = self._messages[idx]
            if msg["role"] == "assistant" and msg.get("tool_calls"):
                break
            if msg["role"] in ("user", "assistant"):
                return
            idx -= 1
        if idx >= 0:
            del self._messages[idx:]

    def repair_orphaned_tool_calls(self):
        """
        修复孤立的 tool_calls 和 tool 消息。
        API 要求：assistant(tool_calls) 后面必须紧跟 tool 消息。
        """
        # 第一轮：收集所有有效（有配对）的 tool_call_id
        valid_tc_ids = set()
        i = 0
        while i < len(self._messages):
            msg = self._messages[i]
            if msg["role"] == "assistant" and msg.get("tool_calls") and not msg.get("content"):
                expected_ids = {tc["id"] for tc in msg["tool_calls"]}
                j = i + 1
                found_ids = set()
                while j < len(self._messages) and self._messages[j]["role"] == "tool":
                    found_ids.add(self._messages[j].get("tool_call_id", ""))
                    j += 1
                if expected_ids <= found_ids:
                    valid_tc_ids.update(found_ids)
                i = j
            else:
                i += 1

        # 第二轮：过滤掉孤立的消息
        repaired = []
        i = 0
        while i < len(self._messages):
            msg = self._messages[i]
            if msg["role"] == "assistant" and msg.get("tool_calls") and not msg.get("content"):
                expected_ids = {tc["id"] for tc in msg["tool_calls"]}
                j = i + 1
                found_ids = set()
                while j < len(self._messages) and self._messages[j]["role"] == "tool":
                    found_ids.add(self._messages[j].get("tool_call_id", ""))
                    j += 1
                if expected_ids <= found_ids:
                    repaired.append(msg)
                    repaired.extend(self._messages[i + 1:j])
                # 否则跳过（孤立的 tool_calls + 不完整的 tool 消息）
                i = j
            elif msg["role"] == "tool":
                if msg.get("tool_call_id") in valid_tc_ids:
                    repaired.append(msg)
                # 否则跳过孤立的 tool 消息
                i += 1
            else:
                repaired.append(msg)
                i += 1

        removed = len(self._messages) - len(repaired)
        if removed > 0:
            self._messages = repaired
        return removed > 0

    def add_tool_result(self, tool_call_id: str, name: str, content: str,
                        action: str | None = None):
        """
        添加工具执行结果（tool role 消息）
        完整存入，不截断 — 截断会导致 Agent 基于残缺内容做出错误决策。
        上下文预算由 ConversationStore.load() 的整条丢弃策略管理。
        """

        msg = {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": content,
        }
        self._messages.append(msg)
        self._trim()

    def get_messages(self) -> list[dict]:
        """
        获取完整的消息列表（含 system prompt）

        Returns:
            [system_message, ...history_messages]
        """
        messages = []
        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})

        for msg in self._messages:
            # 删除内部标记和元数据，不暴露给 LLM
            keep = {k: v for k, v in msg.items() if not k.startswith("_") and k not in ("ts",)}
            messages.append(keep)

        return messages

    def get_system_prompt(self) -> str | None:
        """获取系统提示词"""
        return self._system_prompt

    def set_messages(self, messages: list[dict]):
        """设置消息列表（用于加载历史对话）"""
        self._messages = list(messages)

    def extract_old_messages(self, keep_recent: int = 15) -> list[dict]:
        """提取早期消息（用于 LLM 压缩）

        Args:
            keep_recent: 保留最近 N 轮对话不压缩

        Returns:
            被提取的早期消息列表（不含 tool 消息，只保留对话轮次）
        """
        # 找到最近 keep_recent 轮的起始位置
        user_count = 0
        split_idx = len(self._messages)
        for i in range(len(self._messages) - 1, -1, -1):
            if self._messages[i]["role"] == "user":
                user_count += 1
                if user_count > keep_recent:
                    split_idx = i
                    break

        if split_idx <= 0:
            return []

        old_messages = self._messages[:split_idx]

        # 只保留对话轮次（user + assistant），过滤 tool 和已有摘要
        conversation_messages = []
        for msg in old_messages:
            if msg.get("_is_summary"):
                continue  # 跳过已有摘要，防止重复压缩
            if msg["role"] == "user":
                conversation_messages.append(msg)
            elif msg["role"] == "assistant" and msg.get("content"):
                conversation_messages.append({
                    "role": "assistant",
                    "content": msg["content"],
                })

        return conversation_messages

    def replace_old_with_summary(self, summary: str, keep_recent: int = 15):
        """用摘要替换早期消息

        Args:
            summary: LLM 生成的摘要文本
            keep_recent: 保留最近 N 轮对话
        """
        # 找到最近 keep_recent 轮的起始位置
        user_count = 0
        split_idx = len(self._messages)
        for i in range(len(self._messages) - 1, -1, -1):
            if self._messages[i]["role"] == "user":
                user_count += 1
                if user_count > keep_recent:
                    split_idx = i
                    break

        if split_idx <= 0:
            return

        # 保留最近的消息
        recent_messages = self._messages[split_idx:]

        # 构建新的消息列表：summary + 最近消息
        self._messages = [
            {"role": "assistant", "content": f"[历史摘要] {summary}", "_is_summary": True},
            *recent_messages,
        ]

    def clear(self):
        """清空对话历史（保留 system prompt）"""
        self._messages.clear()

    def get_history(self) -> list[dict]:
        """获取不含 system prompt 的历史消息"""
        return list(self._messages)

    @property
    def turn_count(self) -> int:
        """当前轮数（粗略计算：user 消息数）"""
        return sum(1 for m in self._messages if m["role"] == "user")

    def _trim(self):
        """
        滑动窗口裁剪

        保留最近 max_turns 轮的 messages。
        安全切割：不会切断 tool_calls → tool_results 的关联。
        """
        max_messages = self.max_turns * 4  # 每轮最多：user + assistant(tool_calls) + N*tool_result
        if len(self._messages) <= max_messages:
            return

        excess = len(self._messages) - max_messages

        # 从 excess 位置往前找一个安全的切割点
        # 安全点 = 一个 "user" 消息之前，或一个带 content 的 "assistant" 消息之前
        # 不能切在 tool_result 序列中间（会导致 orphan tool_results）
        cut_index = excess

        # 如果 cut_index 落在 tool 消息序列中，往前跳到这个序列的开始
        while cut_index > 0 and self._messages[cut_index]["role"] == "tool":
            cut_index -= 1

        # 如果 cut_index 落在一个 assistant(tool_calls) 消息上，
        # 它的 tool_results 已经被切掉了，所以也要跳过
        if cut_index > 0 and self._messages[cut_index]["role"] == "assistant":
            msg = self._messages[cut_index]
            if msg.get("tool_calls") and not msg.get("content"):
                # 这是一个纯 tool_calls 的 assistant 消息，检查后面是否还有对应的 tool_result
                has_following_tools = (
                    cut_index + 1 < len(self._messages)
                    and self._messages[cut_index + 1]["role"] == "tool"
                )
                if not has_following_tools:
                    # tool_results 已被切掉，这个 assistant(tool_calls) 也没用了
                    cut_index += 1

        if cut_index > 0:
            self._messages = self._messages[cut_index:]

    def __len__(self):
        return len(self._messages)

    def __bool__(self):
        """ConversationMemory 实例始终为 True（即使消息为空）"""
        return True

    def __repr__(self):
        return (
            f"<ConversationMemory turns={self.turn_count} "
            f"messages={len(self._messages)} max_turns={self.max_turns}>"
        )
