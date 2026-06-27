"""
对话管理接口

职责: 参数校验 → 调服务层 → JSON 响应
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from api.dependencies import AppState, get_app_state
from services import conversation_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("")
async def list_conversations(
    page: int = 1, page_size: int = 20,
    state: AppState = Depends(get_app_state),
):
    return conversation_service.list_conversations(state.store, page, page_size)


@router.post("")
async def create_conversation(state: AppState = Depends(get_app_state)):
    return conversation_service.create_conversation(state.store, state.config.max_turns)


@router.get("/{conv_id}")
async def get_conversation(conv_id: str, state: AppState = Depends(get_app_state)):
    try:
        return conversation_service.get_conversation(state.store, conv_id)
    except FileNotFoundError:
        raise HTTPException(404, f"对话 {conv_id} 不存在")


@router.delete("/{conv_id}")
async def delete_conversation(conv_id: str, state: AppState = Depends(get_app_state)):
    if conversation_service.delete_conversation(state.store, conv_id):
        return {"status": "deleted", "id": conv_id}
    raise HTTPException(404, f"对话 {conv_id} 不存在")
