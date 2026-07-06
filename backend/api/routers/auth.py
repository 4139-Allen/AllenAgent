"""
认证接口 — 注册、登录、刷新、登出、用户信息
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.dependencies import get_db, get_current_user
from api.schemas.auth import (
    RegisterRequest, LoginRequest, RefreshRequest,
    LoginResponse, TokenResponse, UserResponse,
)
from services import auth_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=LoginResponse)
async def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """注册新用户"""
    try:
        result = auth_service.register(db, body.phone, body.password, body.name)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    """手机号+密码登录"""
    try:
        result = auth_service.login(db, body.phone, body.password)
        return result
    except ValueError as e:
        raise HTTPException(401, str(e))


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    """用 refresh token 换新 access token"""
    try:
        result = auth_service.refresh_token(db, body.refresh_token)
        return result
    except ValueError as e:
        raise HTTPException(401, str(e))


@router.post("/logout")
async def logout(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """登出当前设备"""
    # 简单实现：清除该用户所有 session
    # 如果要仅登出当前设备，前端需传 refresh_token
    auth_service.logout(db, current_user["id"])
    return {"status": "ok"}


@router.get("/me", response_model=UserResponse)
async def me(current_user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    return current_user
