"""
对话持久化（JSONL 格式）
每行一个 JSON 对象，第一行是元数据，后续是消息

存储策略：
- 压缩由 AllenAgent 在会话进行中触发（LLM 生成摘要）
- summary 行写入 JSONL，替代旧消息
- save() 时完整写入当前内存状态

加载策略（智能上下文窗口感知，完整优先）：
- summary 记录 → 早期对话的压缩摘要
- 最近 N 轮对话 → 能塞进上下文窗口就全塞
- 不截断工具结果（截断会导致 Agent 基于残缺内容做错误决策）
- 装不下的从最早的消息开始整条丢弃
"""

import copy
import json
import logging
import time
from pathlib import Path

from memory.short_term import ConversationMemory
from utils.token_counter import estimate_message_tokens

logger = logging.getLogger(__name__)

# 对话存储目录
CONVERSATIONS_DIR = Path(__file__).parent.parent / "conversations"
# 截断标记 — save() 据此拒绝写入已截断的数据
TRUNCATED_MARKER = "\n...(截断)"


class ConversationStore:
    """对话持久化存储（JSONL 格式）"""

    def save(self, memory: ConversationMemory = None, conversation_id: str = None,
             title: str = None, full_history: list[dict] = None) -> str:
        """保存对话到 JSONL 文件（完整写入）

        Args:
            memory: ConversationMemory（全量保存其消息，与 full_history 二选一）
            conversation_id: 对话 ID
            title: 对话标题
            full_history: 完整消息列表（用于展示层全量保存，优先于 memory）
        """
        if conversation_id is None:
            conversation_id = time.strftime("%Y%m%d_%H%M%S")

        # 确定消息来源：full_history（展示层全量）> memory（推理层）
        if full_history is not None:
            messages = full_history
        elif memory is not None:
            messages = memory.get_history()
        else:
            messages = []

        if title is None:
            for msg in messages:
                if msg.get("role") == "user" and msg.get("content"):
                    title = msg["content"][:50]
                    break
            if not title:
                title = f"对话 {conversation_id}"

        CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
        filepath = CONVERSATIONS_DIR / f"{conversation_id}.jsonl"

        # 构建 JSONL 行
        lines = []
        # 第一行：元数据（保留已有 pin 状态）
        old_pinned = False
        if filepath.exists():
            try:
                old_meta = json.loads(filepath.read_text(encoding="utf-8").splitlines()[0])
                old_pinned = old_meta.get("pinned", False)
            except Exception:
                pass
        meta = {
            "type": "meta",
            "id": conversation_id,
            "title": title,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "pinned": old_pinned,
        }
        lines.append(json.dumps(meta, ensure_ascii=False))

        # 后续行：消息
        truncated_count = 0
        for msg in messages:
            # ── 防御：拒绝写入已截断的工具结果 ──
            # 如果 content 包含截断标记，说明这是经过 load() 截断过的数据，
            # 不应持久化到 JSONL（会永久丢失完整内容）。
            # 跳过这些行，让下次 save() 从完整源重新构建。
            if msg.get("role") == "tool":
                content = msg.get("content", "")
                if TRUNCATED_MARKER in content:
                    truncated_count += 1
                    continue

            line = self._message_to_jsonl(msg)
            lines.append(json.dumps(line, ensure_ascii=False))

        if truncated_count:
            logger.warning(
                "save() 跳过了 %d 条已截断的工具结果（完整内容已被覆盖，无法恢复）",
                truncated_count,
            )

        filepath.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return conversation_id

    def append_summary(self, conversation_id: str, summary: str):
        """替换最后一条 summary 行（避免重复累计）

        Args:
            conversation_id: 对话 ID
            summary: LLM 生成的摘要文本
        """
        filepath = CONVERSATIONS_DIR / f"{conversation_id}.jsonl"
        if not filepath.exists():
            return

        summary_line = json.dumps({
            "type": "summary",
            "summary": summary,
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, ensure_ascii=False)

        lines = filepath.read_text(encoding="utf-8").splitlines()
        # 找到最后一条 summary 行并替换，没有则追加
        replaced = False
        for i in range(len(lines) - 1, -1, -1):
            if not lines[i].strip():
                continue
            try:
                obj = json.loads(lines[i])
                if obj.get("type") == "summary":
                    lines[i] = summary_line
                    replaced = True
                    break
            except json.JSONDecodeError:
                continue
        if not replaced:
            lines.append(summary_line)
        filepath.write_text("\n".join(lines) + "\n", encoding="utf-8")

    LOAD_RATIO = 0.95

    def load(
        self,
        conversation_id: str,
        max_turns: int = 10,
        context_window: int = 0,
        fixed_overhead_tokens: int = 0,
    ) -> ConversationMemory:
        """从 JSONL 文件加载对话（系统提示词运行时动态注入）

        智能加载策略（完整优先）：

        1. 把 JSONL 中的所有行读入内存
        2. 分离出 summary 行和普通消息行
        3. 计算可用 token 预算：
           available = context_window - fixed_overhead_tokens
        4. 有 summary 时：
           - 保留 summary（约几百 token）
           - 从最新的消息开始往前加载，直到塞满可用预算
        5. 无 summary 时：
           - 从最新的消息开始往前加载，直到塞满可用预算
           - 无法容纳的旧消息直接丢弃
        6. **不截断任何消息** — 留下的每条都是完整的。
           装不下的整条丢弃而非切一半，确保 LLM 不会基于残缺内容做决策。
           若需要完整文件内容，LLM 可随时调 file_io 重新读取。

        Args:
            conversation_id: 对话 ID
            max_turns: ConversationMemory 的滑动窗口上限
            context_window: 模型上下文窗口（0 = 不限制，加载全部）
            fixed_overhead_tokens: system_prompt + Allen.md 等固定占用的 token

        Returns:
            加载好的 ConversationMemory
        """
        filepath = CONVERSATIONS_DIR / f"{conversation_id}.jsonl"
        if not filepath.exists():
            raise FileNotFoundError(f"对话 '{conversation_id}' 不存在")

        # ── 1. 读取全部行 ────────────────────────
        summaries: list[dict] = []
        raw_messages: list[dict] = []

        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = obj.get("type")
            if msg_type == "meta":
                continue
            elif msg_type == "summary":
                summaries.append(obj)
            elif msg_type in ("user", "assistant", "tool", "tool_call", "tool_result", "thought"):
                msg = self._jsonl_to_message(obj)
                if msg:
                    raw_messages.append(msg)

        # ── 2. 构建最终消息列表 ──────────────────
        result_messages: list[dict] = []

        # 2a. 有 summary → 作为第一条消息
        last_summary_text = None
        for s in reversed(summaries):
            text = s.get("summary", "").strip()
            if text:
                last_summary_text = text
                break
        if last_summary_text:
            result_messages.append({
                "role": "assistant",
                "content": f"[历史摘要] {last_summary_text}",
                "_is_summary": True,
            })

        # 2b. 从后往前加载消息，直到塞满上下文
        #
        # 设计原则：每条消息要么完整，要么不出现。
        #   - 不截断工具结果（过往截断曾导致 Agent 基于残缺内容做决策，
        #     如恢复文件时因缺少后半部分而恢复不全）
        #   - 装不下时丢弃整条最早的消息，而不是每条切一半
        #   - 完整内容始终可从 JSONL 或重新读取获得
        if context_window > 0:
            available = int(context_window * self.LOAD_RATIO)
            used_tokens = fixed_overhead_tokens
            if last_summary_text:
                used_tokens += estimate_message_tokens(result_messages[0])

            for msg in reversed(raw_messages):
                # 拷贝而非引用，绝不修改 raw_messages 中的原始数据
                msg = copy.deepcopy(msg)

                msg_tokens = estimate_message_tokens(msg)
                if used_tokens + msg_tokens > available:
                    break  # 装不下了，丢弃这条及更早的消息
                result_messages.append(msg)
                used_tokens += msg_tokens

            # 反转回正常顺序（从旧到新）
            if last_summary_text:
                # summary 保留在开头，其余从旧到新
                result_messages = result_messages[:1] + list(reversed(result_messages[1:]))
            else:
                # 全部反转
                result_messages = list(reversed(result_messages))
        else:
            # 不限制上下文 → 加载全部
            result_messages.extend(raw_messages)

        memory = ConversationMemory(max_turns=max_turns)
        memory._messages = result_messages
        return memory

    def load_display(self, conversation_id: str) -> list[dict]:
        """加载完整对话历史（无预算限制，用于 ChatPanel 展示）

        返回所有 user/assistant/tool 消息，跳过 meta 行。
        summary 行转为系统消息以便展示。
        不截断工具结果，保留完整内容。

        Args:
            conversation_id: 对话 ID

        Returns:
            完整的消息列表（从旧到新）
        """
        filepath = CONVERSATIONS_DIR / f"{conversation_id}.jsonl"
        if not filepath.exists():
            raise FileNotFoundError(f"对话 '{conversation_id}' 不存在")

        messages: list[dict] = []

        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = obj.get("type")

            if msg_type == "meta":
                continue

            elif msg_type == "summary":
                # summary 转为系统消息展示
                summary_text = obj.get("summary", "")
                if summary_text:
                    messages.append({
                        "role": "system",
                        "content": f"📋 历史摘要：{summary_text}",
                        "_is_summary": True,
                    })

            elif msg_type in ("user", "assistant", "tool", "tool_call", "tool_result", "thought"):
                msg = self._jsonl_to_message(obj)
                if msg:
                    messages.append(msg)

        return messages

    def list_all(self) -> list[dict]:
        """列出所有对话（只读第一行 meta）"""
        if not CONVERSATIONS_DIR.exists():
            return []

        conversations = []
        for filepath in sorted(CONVERSATIONS_DIR.glob("*.jsonl"), reverse=True):
            try:
                first_line = filepath.read_text(encoding="utf-8").splitlines()[0].strip()
                meta = json.loads(first_line)
                if meta.get("type") == "meta":
                    size = filepath.stat().st_size
                    conversations.append({
                        "id": meta.get("id", filepath.stem),
                        "title": meta.get("title", "未命名"),
                        "created_at": meta.get("created_at", ""),
                        "turn_count": self._count_turns(filepath),
                        "file_size": size,
                        "pinned": meta.get("pinned", False),
                    })
            except (json.JSONDecodeError, IndexError, KeyError):
                continue
        # 置顶排最前，按创建时间倒序（最新的在最上面）
        conversations.sort(key=lambda c: c.get("created_at", "") or "", reverse=True)
        conversations.sort(key=lambda c: not c.get("pinned", False))
        return conversations

    def delete(self, conversation_id: str) -> bool:
        """删除对话文件"""
        filepath = CONVERSATIONS_DIR / f"{conversation_id}.jsonl"
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def toggle_pin(self, conversation_id: str) -> bool:
        """切换置顶状态，返回新的 pin 状态"""
        filepath = CONVERSATIONS_DIR / f"{conversation_id}.jsonl"
        if not filepath.exists():
            raise FileNotFoundError(f"对话 '{conversation_id}' 不存在")

        lines = filepath.read_text(encoding="utf-8").splitlines()
        if not lines:
            raise ValueError("对话文件为空")

        meta = json.loads(lines[0])
        current = meta.get("pinned", False)
        meta["pinned"] = not current
        lines[0] = json.dumps(meta, ensure_ascii=False)
        filepath.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return not current

    def _count_turns(self, filepath: Path) -> int:
        """统计对话轮数"""
        count = 0
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if obj.get("type") == "user":
                    count += 1
            except json.JSONDecodeError:
                continue
        return count

    def _message_to_jsonl(self, msg: dict) -> dict:
        """将 ConversationMemory 消息转为 JSONL 格式"""
        role = msg.get("role", "")
        # 优先使用消息自带的时间戳，没有才用当前时间
        ts = msg.get("ts", time.strftime("%Y-%m-%d %H:%M:%S"))

        if role == "user":
            return {"type": "user", "content": msg.get("content", ""), "ts": ts}
        elif role == "assistant":
            if msg.get("_is_summary"):
                content = msg.get("content", "")
                summary_text = content.replace("[历史摘要] ", "", 1) if content.startswith("[历史摘要]") else content
                return {"type": "summary", "summary": summary_text, "ts": ts}
            if msg.get("tool_calls"):
                tc = msg["tool_calls"][0]
                func = tc.get("function", {})
                try:
                    args = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                return {
                    "type": "tool_call",
                    "id": tc.get("id", ""),
                    "name": func.get("name", ""),
                    "args": args,
                    "ts": ts,
                }
            else:
                content = msg.get("content", "")
                line = {"type": "assistant", "content": content, "ts": ts}
                thinking = msg.get("_thinking", "")
                if thinking.strip():
                    line["thinking"] = thinking
                return line
        elif role == "tool":
            line = {
                "type": "tool_result",
                "id": msg.get("tool_call_id", ""),
                "content": msg.get("content", ""),
            }
            return line
        elif role == "system":
            if msg.get("_is_summary"):
                content = msg.get("content", "")
                # 去掉展示层添加的前缀
                for prefix in ["📋 历史摘要：", "📋 ", "[历史摘要] "]:
                    if content.startswith(prefix):
                        content = content[len(prefix):]
                        break
                return {"type": "summary", "summary": content, "ts": ts}
            return {"type": "system", "content": msg.get("content", ""), "ts": ts}
        elif role == "thought":
            return {
                "type": "thought",
                "segments": msg.get("segments", []),
                "elapsed": msg.get("elapsed", 0),
            }
        return {"type": "unknown", "content": str(msg)}

    def _jsonl_to_message(self, obj: dict) -> dict | None:
        """将 JSONL 对象转为 ConversationMemory 消息格式"""
        msg_type = obj.get("type")

        if msg_type == "user":
            msg = {"role": "user", "content": obj.get("content", "")}
        elif msg_type == "assistant":
            msg = {"role": "assistant", "content": obj.get("content", "")}
            thinking = obj.get("thinking", "")
            if thinking:
                msg["_thinking"] = thinking
        elif msg_type == "tool_call":
            msg = {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": obj.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": obj.get("name", ""),
                        "arguments": json.dumps(obj.get("args", {}), ensure_ascii=False),
                    },
                }],
            }
        elif msg_type == "tool_result":
            msg = {
                "role": "tool",
                "tool_call_id": obj.get("id", ""),
                "content": obj.get("content", ""),
            }
        elif msg_type == "thought":
            msg = {
                "role": "thought",
                "segments": obj.get("segments", []),
                "elapsed": obj.get("elapsed", 0),
            }
        else:
            return None

        # 保留时间戳（如有）
        if "ts" in obj:
            msg["ts"] = obj["ts"]
        return msg
