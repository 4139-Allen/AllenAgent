"""
数据库版对话存储 — 替代 JSONL，API 接口兼容 ConversationStore

表结构（定义在 db/models.py）：
  conversations — 对话元信息
  messages      — 每条消息一行
"""

import json
import logging
import time
from pathlib import Path
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from db.database import SessionLocal
from db.models import Conversation, Message
from memory.short_term import ConversationMemory
from utils.token_counter import estimate_message_tokens

logger = logging.getLogger(__name__)

TRUNCATED_MARKER = "\n...(截断)"


class DbConversationStore:
    """数据库版对话持久化存储"""

    LOAD_RATIO = 0.95

    def __init__(self, db: Session | None = None):
        self._db = db

    def _get_db(self) -> Session:
        return self._db or SessionLocal()

    # ── 保存对话 ────────────────────────────────────────────

    def save(self, memory: ConversationMemory = None, conversation_id: str = None,
             title: str = None, full_history: list[dict] = None,
             user_id: str = None) -> str:
        """
        保存对话到数据库

        Args:
            memory: ConversationMemory
            conversation_id: 对话 ID（不传则新建）
            title: 对话标题
            full_history: 完整消息列表（优先于 memory）
            user_id: 用户 ID（新建对话时必需）

        Returns:
            conversation_id
        """
        db = self._get_db()
        try:
            # ── 确定消息来源 ──
            if full_history is not None:
                messages_data = full_history
            elif memory is not None:
                messages_data = memory.get_history()
            else:
                messages_data = []

            # ── 确定标题 ──
            if title is None:
                for msg in messages_data:
                    if msg.get("role") == "user" and msg.get("content"):
                        title = str(msg["content"])[:50]
                        break
                if not title:
                    title = f"对话 {conversation_id or int(time.time())}"

            # ── 查找或创建对话 ──
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")

            if conversation_id:
                conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
                if conv:
                    conv.title = title
                    conv.updated_at = now
                    # 删除旧消息
                    db.query(Message).filter(Message.conversation_id == conversation_id).delete()
                else:
                    conv = Conversation(
                        id=conversation_id,
                        user_id=user_id or "",
                        title=title,
                        created_at=now,
                        updated_at=now,
                    )
                    db.add(conv)
            else:
                import uuid
                conversation_id = str(uuid.uuid4())
                conv = Conversation(
                    id=conversation_id,
                    user_id=user_id or "",
                    title=title,
                    created_at=now,
                    updated_at=now,
                )
                db.add(conv)

            db.flush()

            # ── 写入消息 ──
            for msg in messages_data:
                self._write_message(db, conversation_id, msg)

            db.commit()
            return conversation_id

        except Exception:
            db.rollback()
            raise
        finally:
            if not self._db:
                db.close()

    def _write_message(self, db: Session, conversation_id: str, msg: dict):
        """将单条消息写入 messages 表"""
        role = msg.get("role", "")
        content = msg.get("content")

        # 构建 metadata（存放非标准字段）
        metadata = {}
        if role == "assistant":
            thinking = msg.get("_thinking", "")
            if thinking:
                metadata["thinking"] = thinking
            if msg.get("tool_calls"):
                metadata["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "function": tc["function"],
                        "arguments": tc["arguments"],
                    } for tc in msg["tool_calls"]
                ]
        elif role == "tool_call":
            metadata["tool_calls"] = [{
                "id": msg.get("tool_call_id", ""),
                "function": msg.get("name", ""),
                "arguments": msg.get("args", {}),
            }]
        elif role == "tool_result":
            metadata["tool_call_id"] = msg.get("tool_call_id", "")
        elif role == "thought":
            metadata["segments"] = msg.get("segments", [])
            metadata["elapsed"] = msg.get("elapsed", 0)

        # 跳过已截断的工具结果
        if role == "tool" and content and TRUNCATED_MARKER in str(content):
            logger.warning("跳过已截断的工具结果")
            return

        # 确定实际 role（标准化）
        db_role = role
        if role == "assistant" and msg.get("tool_calls"):
            db_role = "tool_call"
            content = None
        elif role == "tool":
            db_role = "tool_result"

        message = Message(
            conversation_id=conversation_id,
            role=db_role,
            content=str(content) if content else None,
            msg_metadata=json.dumps(metadata, ensure_ascii=False),
            token_count=estimate_message_tokens(msg),
            created_at=msg.get("ts", datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        db.add(message)

    # ── 加载对话 ────────────────────────────────────────────

    def load(self, conversation_id: str, max_turns: int = 10,
             context_window: int = 0,
             fixed_overhead_tokens: int = 0) -> ConversationMemory:
        """从数据库加载对话"""
        db = self._get_db()
        try:
            conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
            if not conv:
                raise FileNotFoundError(f"对话 '{conversation_id}' 不存在")

            rows = db.query(Message).filter(
                Message.conversation_id == conversation_id
            ).order_by(Message.created_at).all()

            # 转换消息格式
            summaries: list[str] = []
            raw_messages: list[dict] = []

            for row in rows:
                msg = self._row_to_message(row)
                if msg is None:
                    continue
                if msg.get("_is_summary"):
                    summaries.append(msg.get("content", ""))
                else:
                    raw_messages.append(msg)

            # 构建消息列表（同 JSONL 版逻辑）
            result_messages: list[dict] = []

            last_summary = summaries[-1] if summaries else None
            if last_summary:
                result_messages.append({
                    "role": "assistant",
                    "content": f"[历史摘要] {last_summary}",
                    "_is_summary": True,
                })

            if context_window > 0:
                available = int(context_window * self.LOAD_RATIO)
                used_tokens = fixed_overhead_tokens
                if last_summary:
                    used_tokens += estimate_message_tokens(result_messages[0])

                for msg in reversed(raw_messages):
                    import copy
                    msg = copy.deepcopy(msg)
                    msg_tokens = estimate_message_tokens(msg)
                    if used_tokens + msg_tokens > available:
                        break
                    result_messages.append(msg)
                    used_tokens += msg_tokens

                if last_summary:
                    result_messages = result_messages[:1] + list(reversed(result_messages[1:]))
                else:
                    result_messages = list(reversed(result_messages))
            else:
                result_messages.extend(raw_messages)

            memory = ConversationMemory(max_turns=max_turns)
            memory._messages = result_messages
            return memory

        finally:
            if not self._db:
                db.close()

    def load_display(self, conversation_id: str) -> list[dict]:
        """加载完整对话历史（无预算限制，用于 UI 展示）"""
        db = self._get_db()
        try:
            rows = db.query(Message).filter(
                Message.conversation_id == conversation_id
            ).order_by(Message.created_at).all()

            messages: list[dict] = []
            for row in rows:
                msg = self._row_to_message(row)
                if msg:
                    # summary 转系统消息
                    if msg.get("_is_summary"):
                        summary_text = msg.get("content", "").replace("[历史摘要] ", "", 1)
                        if summary_text:
                            messages.append({
                                "role": "system",
                                "content": f"📋 历史摘要：{summary_text}",
                                "_is_summary": True,
                            })
                    else:
                        messages.append(msg)
            return messages

        finally:
            if not self._db:
                db.close()

    def _row_to_message(self, row: Message) -> dict | None:
        """将 DB 行转为 ConversationMemory 消息格式"""
        meta = {}
        if row.msg_metadata and row.msg_metadata != "{}":
            try:
                meta = json.loads(row.msg_metadata)
            except json.JSONDecodeError:
                meta = {}

        if row.role == "user":
            return {"role": "user", "content": row.content or "", "ts": row.created_at}

        elif row.role == "assistant":
            msg = {"role": "assistant", "content": row.content or "", "ts": row.created_at}
            thinking = meta.get("thinking", "")
            if thinking:
                msg["_thinking"] = thinking
            return msg

        elif row.role == "tool_call":
            tcs = meta.get("tool_calls", [])
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["function"],
                            "arguments": tc.get("arguments", "{}"),
                        },
                    }
                    for tc in tcs
                ],
                "ts": row.created_at,
            }

        elif row.role == "tool_result":
            return {
                "role": "tool",
                "tool_call_id": meta.get("tool_call_id", ""),
                "content": row.content or "",
                "ts": row.created_at,
            }

        elif row.role == "thought":
            return {
                "role": "thought",
                "segments": meta.get("segments", []),
                "elapsed": meta.get("elapsed", 0),
                "ts": row.created_at,
            }

        elif row.role == "summary":
            return {
                "role": "assistant",
                "content": f"[历史摘要] {row.content or ''}",
                "_is_summary": True,
                "ts": row.created_at,
            }

        return None

    # ── 列表演示 ────────────────────────────────────────────

    def list_all(self, user_id: str | None = None) -> list[dict]:
        """列出对话（按用户过滤，置顶最前，按时间倒序）"""
        db = self._get_db()
        try:
            query = db.query(Conversation)
            if user_id:
                query = query.filter(Conversation.user_id == user_id)

            conversations = []
            for conv in query.order_by(
                Conversation.pinned.desc(),
                Conversation.created_at.desc(),
            ).all():
                turn_count = db.query(Message).filter(
                    Message.conversation_id == conv.id,
                    Message.role == "user",
                ).count()

                conversations.append({
                    "id": conv.id,
                    "title": conv.title or "新对话",
                    "created_at": conv.created_at,
                    "turn_count": turn_count,
                    "pinned": bool(conv.pinned),
                    "file_size": 0,  # 兼容 JSONL 接口
                })
            return conversations

        finally:
            if not self._db:
                db.close()

    def delete(self, conversation_id: str) -> bool:
        """删除对话（级联删除消息）"""
        db = self._get_db()
        try:
            conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
            if not conv:
                return False
            db.delete(conv)  # ON DELETE CASCADE 会自动删 messages
            db.commit()
            return True
        except Exception:
            db.rollback()
            return False
        finally:
            if not self._db:
                db.close()

    def toggle_pin(self, conversation_id: str) -> bool:
        """切换置顶状态"""
        db = self._get_db()
        try:
            conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
            if not conv:
                raise FileNotFoundError(f"对话 '{conversation_id}' 不存在")
            conv.pinned = 0 if conv.pinned else 1
            db.commit()
            return bool(conv.pinned)
        except Exception:
            db.rollback()
            raise
        finally:
            if not self._db:
                db.close()
