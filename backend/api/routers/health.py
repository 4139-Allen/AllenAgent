import time
from fastapi import APIRouter, Depends
from api.dependencies import AppState, get_app_state

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(state: AppState = Depends(get_app_state)):
    return {
        "status": "ok",
        "timestamp": time.time(),
        "model": state.model_manager.current_model,
        "version": "1.1.0",
    }
