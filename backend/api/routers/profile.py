"""
个人中心接口

职责: 头像、名称、持久记忆 (Allen.md) 管理
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.dependencies import AppState, get_app_state, get_current_user, get_db
from memory.long_term import AllenMemory
from db.models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("")
async def get_profile(
    state: AppState = Depends(get_app_state),
    current_user: dict | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取个人资料（名称、头像、记忆）"""
    mem = AllenMemory(user_id=current_user["id"] if current_user else None)

    name = "ALLen"
    has_avatar = False
    if current_user:
        user = db.query(User).filter(User.id == current_user["id"]).first()
        if user:
            name = user.name or "ALLen"
            has_avatar = user.avatar_data is not None

    return {
        "name": name,
        "avatar": "/api/profile/avatar" if has_avatar else None,
        "memory": mem.get_content(),
        "memory_sections": mem.sections,
    }


class NameUpdate(BaseModel):
    name: str


@router.put("/name")
async def update_name(
    body: NameUpdate,
    current_user: dict | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新显示名称"""
    if not current_user:
        raise HTTPException(401, "请先登录")

    name = body.name.strip()
    if not name:
        raise HTTPException(400, "名称不能为空")
    if len(name) > 50:
        raise HTTPException(400, "名称不能超过50个字符")

    user = db.query(User).filter(User.id == current_user["id"]).first()
    user.name = name
    db.commit()
    return {"status": "ok", "name": name}


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传头像（存入数据库）"""
    if not current_user:
        raise HTTPException(401, "请先登录")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "只支持图片文件")

    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(400, "图片不能超过 2MB")

    user = db.query(User).filter(User.id == current_user["id"]).first()
    user.avatar_data = content
    user.avatar_mime = file.content_type
    db.commit()

    return {"status": "ok", "avatar": "/api/profile/avatar"}


@router.get("/avatar")
async def get_avatar(
    token: str | None = None,
    current_user: dict | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取头像（支持 Bearer 认证 或 ?token=xxx 查询参数，供 <img> 标签使用）"""
    user_id = None

    if current_user:
        user_id = current_user["id"]
    elif token:
        from services.auth_service import decode_access_token
        payload = decode_access_token(token)
        if payload:
            user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(401, "未登录或 token 无效")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.avatar_data:
        raise HTTPException(404, "未设置头像")

    return Response(content=user.avatar_data, media_type=user.avatar_mime or "image/jpeg")


class MemoryUpdate(BaseModel):
    content: str


@router.put("/memory")
async def update_memory(
    body: MemoryUpdate,
    state: AppState = Depends(get_app_state),
    current_user: dict | None = Depends(get_current_user),
):
    """更新持久记忆（完整替换）"""
    mem = AllenMemory(user_id=current_user["id"] if current_user else None)
    try:
        mem.filepath.write_text(body.content, encoding="utf-8")
        mem._load()
        return {"status": "ok", "message": "记忆已更新"}
    except Exception as e:
        raise HTTPException(500, f"保存失败: {e}")


@router.delete("/memory")
async def clear_memory(
    state: AppState = Depends(get_app_state),
    current_user: dict | None = Depends(get_current_user),
):
    """清空持久记忆"""
    mem = AllenMemory(user_id=current_user["id"] if current_user else None)
    mem.clear()
    return {"status": "ok", "message": "记忆已清空"}
