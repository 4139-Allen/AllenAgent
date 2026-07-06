"""
长期记忆接口（按用户隔离）

职责: 参数校验 → 调服务层 → JSON 响应
"""

from fastapi import APIRouter, Depends
from api.dependencies import AppState, get_app_state, get_current_user
from memory.long_term import AllenMemory
from services import memory_service

router = APIRouter(prefix="/memory", tags=["memory"])


def _get_user_memory(current_user: dict | None) -> AllenMemory:
    """获取当前用户的持久记忆"""
    user_id = current_user["id"] if current_user else None
    return AllenMemory(user_id=user_id)


@router.get("")
async def get_memory(
    state: AppState = Depends(get_app_state),
    current_user: dict | None = Depends(get_current_user),
):
    mem = _get_user_memory(current_user)
    return memory_service.get_memory(mem)


@router.post("")
async def add_memory(
    body: dict,
    state: AppState = Depends(get_app_state),
    current_user: dict | None = Depends(get_current_user),
):
    fact = body.get("fact", "").strip()
    if not fact:
        return {"status": "error", "message": "缺少 fact 参数"}
    mem = _get_user_memory(current_user)
    return memory_service.add_memory(mem, fact)
