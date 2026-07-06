"""
认证服务 — 注册、登录、JWT 签发/验证
"""

import uuid
import logging
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from db.models import User, Session as UserSession, Preference

logger = logging.getLogger(__name__)

# ── JWT 配置 ──
# 生产环境请从环境变量读取
SECRET_KEY = "allen-agent-dev-secret-key-do-not-use-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60          # 1 小时
REFRESH_TOKEN_EXPIRE_DAYS = 7             # 7 天

# ── 密码加密 ──
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def _utcnow():
    return datetime.now(timezone.utc)


def _hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _create_access_token(user_id: str) -> tuple[str, int]:
    """创建 access token，返回 (token, expires_in_seconds)"""
    expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = _utcnow() + expires_delta
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "access",
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token, int(expires_delta.total_seconds())


def _create_refresh_token() -> tuple[str, str]:
    """创建 refresh token，返回 (token, expires_at_iso)"""
    expires_delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    expire = _utcnow() + expires_delta
    token = str(uuid.uuid4())  # refresh token 用 UUID，存 DB 可撤销
    return token, expire.isoformat(timespec="seconds")


def _avatar_url(user) -> str:
    """判断用户是否有头像，返回对应的 URL 或空字符串"""
    return "/api/profile/avatar" if user.avatar_data is not None else ""


def decode_access_token(token: str) -> dict | None:
    """解析 access token，返回 payload 或 None"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT 已过期")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning("JWT 无效: %s", e)
        return None


# ═══════════════════════════════════════════════════════════════
# 注册
# ═══════════════════════════════════════════════════════════════
def register(db: Session, phone: str, password: str, name: str = "") -> dict:
    """注册新用户"""
    # 检查手机号是否已注册
    existing = db.query(User).filter(User.phone == phone).first()
    if existing:
        raise ValueError("该手机号已注册")

    # 创建用户
    user = User(
        phone=phone,
        password_hash=_hash_password(password),
        name=name or f"用户{phone[-4:]}",
    )
    db.add(user)
    db.flush()  # 获取 user.id

    # 创建偏好
    pref = Preference(user_id=user.id)
    db.add(pref)

    # 创建 session 和 token
    refresh_token, expires_at = _create_refresh_token()
    session = UserSession(
        user_id=user.id,
        refresh_token=refresh_token,
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()

    access_token, expires_in = _create_access_token(user.id)

    return {
        "user": {
            "id": user.id,
            "phone": user.phone,
            "name": user.name,
            "avatar_url": _avatar_url(user),
            "role": user.role,
            "created_at": user.created_at,
        },
        "token": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": expires_in,
        },
    }


# ═══════════════════════════════════════════════════════════════
# 登录
# ═══════════════════════════════════════════════════════════════
def login(db: Session, phone: str, password: str) -> dict:
    """手机号+密码登录"""
    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        raise ValueError("手机号或密码错误")

    if not user.is_active:
        raise ValueError("账号已被禁用")

    if not _verify_password(password, user.password_hash):
        raise ValueError("手机号或密码错误")

    # 创建新 session
    refresh_token, expires_at = _create_refresh_token()
    session = UserSession(
        user_id=user.id,
        refresh_token=refresh_token,
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()

    access_token, expires_in = _create_access_token(user.id)

    return {
        "user": {
            "id": user.id,
            "phone": user.phone,
            "name": user.name,
            "avatar_url": _avatar_url(user),
            "role": user.role,
            "created_at": user.created_at,
        },
        "token": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": expires_in,
        },
    }


# ═══════════════════════════════════════════════════════════════
# 刷新 token
# ═══════════════════════════════════════════════════════════════
def refresh_token(db: Session, refresh_token_str: str) -> dict:
    """用 refresh token 换新的 access token"""
    session = db.query(UserSession).filter(
        UserSession.refresh_token == refresh_token_str
    ).first()

    if not session:
        raise ValueError("refresh token 无效")

    # 检查是否过期
    expire = datetime.fromisoformat(session.expires_at)
    if expire < _utcnow():
        db.delete(session)
        db.commit()
        raise ValueError("refresh token 已过期，请重新登录")

    user = db.query(User).filter(User.id == session.user_id).first()
    if not user or not user.is_active:
        db.delete(session)
        db.commit()
        raise ValueError("账号不可用")

    # 签发新 access token
    access_token, expires_in = _create_access_token(user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token_str,
        "token_type": "bearer",
        "expires_in": expires_in,
    }


# ═══════════════════════════════════════════════════════════════
# 登出
# ═══════════════════════════════════════════════════════════════
def logout(db: Session, user_id: str, refresh_token_str: str | None = None):
    """登出：清除指定 session 或全部 session"""
    if refresh_token_str:
        session = db.query(UserSession).filter(
            UserSession.refresh_token == refresh_token_str,
            UserSession.user_id == user_id,
        ).first()
        if session:
            db.delete(session)
            db.commit()
    else:
        # 清除该用户所有 session（全部设备登出）
        db.query(UserSession).filter(UserSession.user_id == user_id).delete()
        db.commit()


# ═══════════════════════════════════════════════════════════════
# 获取当前用户
# ═══════════════════════════════════════════════════════════════
def get_user_by_id(db: Session, user_id: str) -> dict | None:
    """根据 ID 获取用户信息"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    return {
        "id": user.id,
        "phone": user.phone,
        "name": user.name,
        "avatar_url": _avatar_url(user),
        "role": user.role,
        "created_at": user.created_at,
    }
