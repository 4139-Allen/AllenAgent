"""
模型管理接口

职责: 参数校验 → 调服务层 → JSON 响应
"""

from fastapi import APIRouter, Depends
from api.dependencies import AppState, get_app_state
from services import model_service

router = APIRouter(prefix="/models", tags=["models"])


@router.get("")
async def list_models(state: AppState = Depends(get_app_state)):
    return model_service.list_models(state.model_manager)


@router.post("/switch")
async def switch_model(body: dict, state: AppState = Depends(get_app_state)):
    name = body.get("model", "").strip()
    if not name:
        return {"status": "error", "message": "缺少 model 参数"}
    return model_service.switch_model(state.model_manager, name)
