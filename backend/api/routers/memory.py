"""
长期记忆接口

职责: 参数校验 → 调服务层 → JSON 响应
"""

from fastapi import APIRouter, Depends
from api.dependencies import AppState, get_app_state
from services import memory_service

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("")
async def get_memory(state: AppState = Depends(get_app_state)):
    return memory_service.get_memory(state.allen_memory)


@router.post("")
async def add_memory(body: dict, state: AppState = Depends(get_app_state)):
    fact = body.get("fact", "").strip()
    if not fact:
        return {"status": "error", "message": "缺少 fact 参数"}
    return memory_service.add_memory(state.allen_memory, fact)
