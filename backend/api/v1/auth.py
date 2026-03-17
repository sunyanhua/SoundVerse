"""
认证相关API
"""
import logging
from datetime import timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.session import get_db
from shared.models.user import User
from shared.schemas.user import (
    WechatLoginRequest,
    Token,
    UserResponse,
    UserQuota,
)
from services.user_service import (
    authenticate_wechat_user,
    create_access_token,
    get_current_user,
    get_user_quota,
)
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_active_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    """
    获取当前认证用户
    """
    user = await get_current_user(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
        )
    return user


async def get_current_user_optional(
    db: AsyncSession = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme),
) -> Optional[User]:
    """
    获取当前用户（可选）
    """
    try:
        user = await get_current_user(db, token)
        return user
    except HTTPException:
        return None


@router.post("/wechat/login", response_model=Token)
async def wechat_login(
    request: WechatLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    微信登录
    """
    try:
        user = await authenticate_wechat_user(db, request.code)

        # 创建访问令牌
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = await create_access_token(
            data={"sub": user.id, "is_admin": user.is_admin},
            expires_delta=access_token_expires,
        )

        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    except Exception as e:
        logger.error(f"微信登录失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="微信登录失败",
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    获取当前用户信息
    """
    return UserResponse(
        **current_user.__dict__,
        is_banned=current_user.is_banned,
    )


@router.get("/quota", response_model=UserQuota)
async def get_user_quota_info(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    获取用户配额信息
    """
    return await get_user_quota(db, current_user.id)


@router.post("/refresh")
async def refresh_token(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    刷新访问令牌
    """
    # 创建新的访问令牌
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = await create_access_token(
        data={"sub": current_user.id, "is_admin": current_user.is_admin},
        expires_delta=access_token_expires,
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    用户登出
    """
    # 在实际实现中，可能需要将令牌加入黑名单
    # 这里简单返回成功
    return {"message": "登出成功"}


@router.get("/test")
async def test_auth(
    current_user: User = Depends(get_current_active_user),
) -> Any:
    """
    测试认证（开发用）
    """
    return {
        "message": "认证成功",
        "user_id": current_user.id,
        "nickname": current_user.nickname,
    }