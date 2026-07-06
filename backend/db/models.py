"""
SQLAlchemy 模型 — 5 张核心表

users       用户账户
sessions    登录态（多设备）
conversations  对话
messages    消息
preferences 用户偏好
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Text, LargeBinary, ForeignKey
from sqlalchemy.orm import relationship
from db.database import Base


def _utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _uuid():
    return str(uuid.uuid4())


# ═══════════════════════════════════════════════════════════════
# 1. users — 用户账户
# ═══════════════════════════════════════════════════════════════
class User(Base):
    __tablename__ = "users"

    id            = Column(String(36), primary_key=True, default=_uuid)
    phone         = Column(String(15), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    name          = Column(String(50), default="", nullable=False)
    avatar_data   = Column(LargeBinary, nullable=True)        # 头像二进制
    avatar_mime   = Column(String(20), default="image/jpeg")  # 图片类型
    role          = Column(String(10), default="user", nullable=False)   # user | admin
    is_active     = Column(Integer, default=1, nullable=False)           # 0=封禁
    created_at    = Column(String(30), default=_utcnow, nullable=False)
    updated_at    = Column(String(30), default=_utcnow, onupdate=_utcnow, nullable=False)

    # 关系
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    sessions      = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    preferences   = relationship("Preference", back_populates="user", uselist=False, cascade="all, delete-orphan")


# ═══════════════════════════════════════════════════════════════
# 2. sessions — 登录态（一人可多设备）
# ═══════════════════════════════════════════════════════════════
class Session(Base):
    __tablename__ = "sessions"

    id            = Column(String(36), primary_key=True, default=_uuid)
    user_id       = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    refresh_token = Column(String(36), unique=True, nullable=False)
    device_info   = Column(Text, default="")
    ip_address    = Column(String(45), default="")
    expires_at    = Column(String(30), nullable=False)    # ISO 时间
    created_at    = Column(String(30), default=_utcnow, nullable=False)

    user = relationship("User", back_populates="sessions")


# ═══════════════════════════════════════════════════════════════
# 3. conversations — 对话
# ═══════════════════════════════════════════════════════════════
class Conversation(Base):
    __tablename__ = "conversations"

    id         = Column(String(36), primary_key=True, default=_uuid)
    user_id    = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title      = Column(Text, default="新对话", nullable=False)
    model      = Column(String(50), default="", nullable=False)    # 使用的模型
    pinned     = Column(Integer, default=0, nullable=False)        # 0/1
    created_at = Column(String(30), default=_utcnow, nullable=False)
    updated_at = Column(String(30), default=_utcnow, onupdate=_utcnow, nullable=False)

    user     = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation",
                            cascade="all, delete-orphan",
                            order_by="Message.created_at")


# ═══════════════════════════════════════════════════════════════
# 4. messages — 消息
# ═══════════════════════════════════════════════════════════════
class Message(Base):
    __tablename__ = "messages"

    id              = Column(String(36), primary_key=True, default=_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    role            = Column(String(20), nullable=False)   # user | assistant | tool_call | tool_result | thought
    content         = Column(Text)                         # 文本内容（tool_call 时为 NULL）
    msg_metadata    = Column("metadata", Text, default="{}")  # JSON：tool_calls / thinking / segments
    token_count     = Column(Integer, default=0)
    created_at      = Column(String(30), default=_utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")


# ═══════════════════════════════════════════════════════════════
# 5. preferences — 用户偏好（一对一）
# ═══════════════════════════════════════════════════════════════
class Preference(Base):
    __tablename__ = "preferences"

    user_id           = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"),
                               primary_key=True)
    theme             = Column(String(10), default="light", nullable=False)
    default_model     = Column(String(50), default="")
    reasoning_effort  = Column(String(10), default="low")
    extra             = Column(Text, default="{}")     # JSON 扩展

    user = relationship("User", back_populates="preferences")
