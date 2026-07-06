"""
认证相关的 Pydantic 模型
"""

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    phone: str = Field(..., pattern=r"^\d{6,15}$", description="手机号")
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    name: str = Field(default="", max_length=50, description="昵称")


class LoginRequest(BaseModel):
    phone: str = Field(..., description="手机号")
    password: str = Field(..., description="密码")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="刷新令牌")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # access token 有效期（秒）


class UserResponse(BaseModel):
    id: str
    phone: str
    name: str
    avatar_url: str
    role: str
    created_at: str


class LoginResponse(BaseModel):
    user: UserResponse
    token: TokenResponse
