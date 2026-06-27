"""
个人中心接口

职责: 头像、名称、持久记忆 (Allen.md) 管理
"""

import json
import logging
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from api.dependencies import AppState, get_app_state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/profile", tags=["profile"])

PROFILE_DIR = Path(__file__).parent.parent.parent / "profile"
PROFILE_FILE = PROFILE_DIR / "profile.json"
AVATAR_DIR = PROFILE_DIR / "avatars"

PROFILE_DIR.mkdir(parents=True, exist_ok=True)
AVATAR_DIR.mkdir(parents=True, exist_ok=True)


def _load_profile() -> dict:
    if PROFILE_FILE.exists():
        try:
            return json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"name": "ALLen"}


def _save_profile(data: dict):
    PROFILE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@router.get("")
async def get_profile(state: AppState = Depends(get_app_state)):
    """获取个人资料（名称、头像、记忆）"""
    profile = _load_profile()
    memory = state.allen_memory
    return {
        "name": profile.get("name", "ALLen"),
        "avatar": "/api/profile/avatar" if (AVATAR_DIR / "avatar.jpg").exists() or (AVATAR_DIR / "avatar.png").exists() else None,
        "memory": memory.get_content() if memory else "",
        "memory_sections": memory.sections if memory else {},
    }


class NameUpdate(BaseModel):
    name: str


@router.put("/name")
async def update_name(body: NameUpdate):
    """更新显示名称"""
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "名称不能为空")
    if len(name) > 50:
        raise HTTPException(400, "名称不能超过50个字符")
    profile = _load_profile()
    profile["name"] = name
    _save_profile(profile)
    return {"status": "ok", "name": name}


@router.post("/avatar")
async def upload_avatar(file: UploadFile = File(...)):
    """上传头像"""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "只支持图片文件")

    ext = "jpg" if "jpeg" in file.content_type else "png"
    filepath = AVATAR_DIR / f"avatar.{ext}"

    # 删除旧头像
    for old in AVATAR_DIR.glob("avatar.*"):
        old.unlink()

    content = await file.read()
    filepath.write_bytes(content)

    return {"status": "ok", "avatar": "/api/profile/avatar"}


@router.get("/avatar")
async def get_avatar():
    """获取头像文件"""
    for ext in ("jpg", "png"):
        path = AVATAR_DIR / f"avatar.{ext}"
        if path.exists():
            from fastapi.responses import FileResponse
            return FileResponse(path)
    raise HTTPException(404, "未设置头像")


class MemoryUpdate(BaseModel):
    content: str


@router.put("/memory")
async def update_memory(body: MemoryUpdate, state: AppState = Depends(get_app_state)):
    """更新持久记忆（完整替换）"""
    if not state.allen_memory:
        raise HTTPException(400, "记忆功能未启用")
    try:
        state.allen_memory.filepath.write_text(body.content, encoding="utf-8")
        state.allen_memory._load()
        return {"status": "ok", "message": "记忆已更新"}
    except Exception as e:
        raise HTTPException(500, f"保存失败: {e}")


@router.delete("/memory")
async def clear_memory(state: AppState = Depends(get_app_state)):
    """清空持久记忆"""
    if not state.allen_memory:
        raise HTTPException(400, "记忆功能未启用")
    state.allen_memory.clear()
    return {"status": "ok", "message": "记忆已清空"}
